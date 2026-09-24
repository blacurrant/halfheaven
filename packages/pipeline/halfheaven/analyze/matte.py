"""Separating the speaker from everything else, fast enough to run on every upload.

Two models, each doing the half it is good at. Measured 2026-09-24 on an M5
over a 720x1280 talking head:

- Robust Video Matting draws the edge: soft, temporally stable alpha that keeps
  real hair, at 37 fps on the Mac GPU. It cannot tell a person from what they
  touch - a table and the phone on it came through as "person".
- MediaPipe's multiclass segmenter decides what the person is, and which parts:
  hair, face skin, body skin, clothes. Its masks are low resolution, so its
  edges are coarse, but it calls a table background.

The subject matte is RVM's alpha inside a widened MediaPipe person mask, which
keeps RVM's hair and drops the table. A two-minute take separates in about two
and a half minutes; SAM2's video mode needed about forty.

Licences: RVM is GPL-3.0 and is fetched at run time through torch.hub, never
vendored. It may run on our own servers; it must never ship in a browser
bundle or a distributed app. MediaPipe and its model are Apache-2.0.

Mattes are written on each take's own frame grid, as grayscale video. The
renderer puts them through the same cuts, crops and zooms as the footage, so
one matte serves every edit made from that take.
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator, Protocol

import cv2
import numpy as np

from halfheaven.media.ffmpeg_bin import ffmpeg
from halfheaven.media.probe import probe
from halfheaven.schemas import TakeMatte

# MediaPipe multiclass classes.
BACKGROUND, HAIR, BODY_SKIN, FACE_SKIN, CLOTHES, OTHERS = range(6)

# The parts change far more slowly than the edge does, and they only gate the
# edge and weight the grade, so they are read on every third frame. That is
# what lets both models fit the time budget on one machine.
PARTS_EVERY = 3
# Segmentation runs at no more than this on the long side. A 4K take matted at
# full size costs 9x the time for an edge that is blurred before use anyway.
MAX_SIDE = 1280
# How far the person mask is grown before it gates RVM, as a share of frame
# height: far enough that it never clips hair RVM found, near enough that a
# table the speaker leans on stays out. 15px at 1280, as measured.
GATE_GROW = 0.012
GATE_SOFTEN = 0.005
SKIN_SOFTEN = 0.004
# Masks are encoded nearly losslessly: they are resampled and composited later.
MASK_CRF = 10

# Pinned to a commit, not the v1.0.0 tag: the tag imports a torchvision module
# that no longer exists. Weights are the v1.0.0 release either way.
RVM_REPO = "PeterL1n/RobustVideoMatting:53d74c6826735f01f4406b5ca9075eee27bec094"
PARTS_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/image_segmenter/"
                   "selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite")


class Matter(Protocol):
    """Soft alpha for one frame, remembering the frames before it."""

    def alpha(self, rgb: np.ndarray) -> np.ndarray:
        """HxW float32 in 0..1 for an HxWx3 uint8 RGB frame."""

    def reset(self) -> None:
        """Forget earlier frames: the next one starts a new take."""


class PartSegmenter(Protocol):
    def parts(self, rgb: np.ndarray, t_ms: int) -> np.ndarray:
        """HxW uint8 class ids (BACKGROUND..OTHERS) for one RGB frame."""


def _device(torch) -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class RvmMatter:
    """Robust Video Matting, mobilenetv3. Its recurrent state is its temporal memory."""

    def __init__(self, device: str | None = None) -> None:
        import torch

        self._torch = torch
        self.device = device or _device(torch)
        self._model = (torch.hub.load(RVM_REPO, "mobilenetv3", trust_repo=True, verbose=False)
                       .eval().to(self.device))
        self._state: list = [None] * 4

    def reset(self) -> None:
        self._state = [None] * 4

    def alpha(self, rgb: np.ndarray) -> np.ndarray:
        torch = self._torch
        height, width = rgb.shape[:2]
        # RVM's guidance: work at roughly 512px on the long side and let its
        # refiner restore the full-resolution edge.
        ratio = min(1.0, 512 / max(height, width))
        with torch.no_grad():
            # Sent as bytes and converted on the device: a quarter of the upload.
            frame = torch.from_numpy(rgb).to(self.device).permute(2, 0, 1)[None].float() / 255
            _, alpha, *self._state = self._model(frame, *self._state, downsample_ratio=ratio)
            return alpha[0, 0].float().cpu().numpy()


def _cache_dir() -> pathlib.Path:
    root = os.environ.get("HALFHEAVEN_CACHE") or pathlib.Path.home() / ".cache" / "halfheaven"
    path = pathlib.Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


class MediaPipeParts:
    """MediaPipe's multiclass selfie segmenter, in video mode."""

    def __init__(self, model: str | pathlib.Path | None = None) -> None:
        from mediapipe.tasks import python as tasks
        from mediapipe.tasks.python import vision

        if model is None:
            model = _cache_dir() / "selfie_multiclass_256x256.tflite"
            if not model.exists():
                partial = model.with_suffix(".part")
                urllib.request.urlretrieve(PARTS_MODEL_URL, partial)
                partial.rename(model)
        import mediapipe

        self._image = mediapipe.Image
        self._format = mediapipe.ImageFormat.SRGB
        self._segmenter = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=tasks.BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.VIDEO,
            output_category_mask=True,
        ))

    def parts(self, rgb: np.ndarray, t_ms: int) -> np.ndarray:
        result = self._segmenter.segment_for_video(
            self._image(image_format=self._format, data=np.ascontiguousarray(rgb)), t_ms)
        return result.category_mask.numpy_view().squeeze().copy()

    def close(self) -> None:
        self._segmenter.close()


# --------------------------------------------------------------------------
# combining the two
# --------------------------------------------------------------------------


def _soft(mask: np.ndarray, grow: float, soften: float) -> np.ndarray:
    """A 0/1 mask grown by `grow` and feathered by `soften` (shares of height), as 0..1.

    Worked at a quarter size: both steps are low-frequency, and at full size
    they cost more than the model they post-process.
    """
    height, width = mask.shape
    small = cv2.resize(mask.astype(np.float32), (max(1, width // 4), max(1, height // 4)),
                       interpolation=cv2.INTER_AREA)
    radius = int(round(grow * height / 4))
    if radius > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
        small = cv2.dilate(small, kernel)
    sigma = soften * height / 4
    if sigma > 0:
        small = cv2.GaussianBlur(small, (0, 0), sigma)
    return np.clip(cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR), 0.0, 1.0)


def person_gate(parts: np.ndarray) -> np.ndarray:
    """Where the subject may be, as 0..1: the person, grown so no hair is lost.

    Never below 1 on the person itself: the feathering belongs outside them, or
    RVM's own edge would be thinned a second time.
    """
    person = parts != BACKGROUND
    return np.maximum(_soft(person, GATE_GROW, GATE_SOFTEN), person)


def skin_weight(parts: np.ndarray) -> np.ndarray:
    """Face and body skin, feathered, as 0..1."""
    return _soft((parts == FACE_SKIN) | (parts == BODY_SKIN), 0.0, SKIN_SOFTEN)


def _to_byte(values: np.ndarray) -> np.ndarray:
    return np.clip(values * 255 + 0.5, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------
# video in, mattes out
# --------------------------------------------------------------------------


def _work_size(width: int, height: int) -> tuple[int, int]:
    scale = min(1.0, MAX_SIDE / max(width, height))
    return (max(2, 2 * round(width * scale / 2)), max(2, 2 * round(height * scale / 2)))


def _frames(take: pathlib.Path, size: tuple[int, int], fps: float) -> Iterator[np.ndarray]:
    """RGB frames on a constant `fps` grid, the same grid the renderer samples.

    Phone footage is often variable-rate; decoding through the fps filter puts
    frame i at i/fps, which is where the matte's frame i will be read back.
    """
    width, height = size
    reader = subprocess.Popen(
        [ffmpeg(), "-v", "error", "-i", str(take), "-an",
         "-vf", f"fps={fps},scale={width}:{height}:flags=area",
         "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    frame_bytes = width * height * 3
    try:
        while True:
            chunk = reader.stdout.read(frame_bytes)
            if len(chunk) < frame_bytes:
                return
            yield np.frombuffer(chunk, np.uint8).reshape(height, width, 3)
    finally:
        reader.stdout.close()
        reader.wait()


def _writer(out: pathlib.Path, size: tuple[int, int], fps: float) -> subprocess.Popen:
    width, height = size
    return subprocess.Popen(
        [ffmpeg(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray",
         "-s", f"{width}x{height}", "-r", f"{fps}", "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", str(MASK_CRF),
         "-pix_fmt", "gray", str(out)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def matte_take(
    take: str | pathlib.Path,
    out_dir: str | pathlib.Path,
    matter: Matter,
    parter: PartSegmenter,
    parts_every: int = PARTS_EVERY,
) -> TakeMatte:
    """Write a subject matte and a skin matte for one take."""
    take, out_dir = pathlib.Path(take), pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    info = probe(take)
    fps = info.fps or 30.0
    size = _work_size(info.width, info.height)
    subject_path = out_dir / f"{take.stem}.subject.mp4"
    skin_path = out_dir / f"{take.stem}.skin.mp4"

    def read_parts(rgb: np.ndarray, t_ms: int) -> tuple[np.ndarray, np.ndarray]:
        parts = parter.parts(rgb, t_ms)
        if parts.shape != rgb.shape[:2]:
            parts = cv2.resize(parts, size, interpolation=cv2.INTER_NEAREST)
        return person_gate(parts), _to_byte(skin_weight(parts))

    subject_out, skin_out = _writer(subject_path, size, fps), _writer(skin_path, size, fps)
    matter.reset()
    # The parts run on the CPU in a worker thread while RVM runs on the GPU:
    # both release the interpreter lock during inference. Each frame waits in
    # `pending` until the parts it is gated by are ready, so nothing is stale.
    pending: deque = deque()
    written = 0

    def flush(wait: bool) -> None:
        nonlocal written
        while pending and (wait or pending[0][1].done()):
            alpha, parts = pending.popleft()
            gate, skin = parts.result()
            subject_out.stdin.write(_to_byte(alpha * gate).tobytes())
            skin_out.stdin.write(skin.tobytes())
            written += 1

    try:
        with ThreadPoolExecutor(max_workers=1) as worker:
            parts = None
            for index, rgb in enumerate(_frames(take, size, fps)):
                if index % parts_every == 0:
                    parts = worker.submit(read_parts, rgb, int(round(index * 1000 / fps)))
                pending.append((matter.alpha(rgb), parts))
                flush(wait=len(pending) > 2 * parts_every)
            flush(wait=True)
    finally:
        for writer in (subject_out, skin_out):
            writer.stdin.close()
            writer.wait()
    if not written:
        raise RuntimeError(f"no frames decoded from {take}")
    return TakeMatte(subject=str(subject_path.resolve()), skin=str(skin_path.resolve()))


def matte_takes(takes: list[str], out_dir: str | pathlib.Path) -> dict[str, TakeMatte]:
    """Every take, keyed by the path as given - which is what VideoClip.src holds."""
    matter, parter = RvmMatter(), MediaPipeParts()
    try:
        return {take: matte_take(take, out_dir, matter, parter) for take in takes}
    finally:
        parter.close()


# --------------------------------------------------------------------------
# running beside the rest of the pipeline
# --------------------------------------------------------------------------


class Matting:
    """Separation started in its own process, collected when the edit needs it.

    Its own process for two reasons: it overlaps reading the reference and
    transcription instead of queueing behind them, and a crash in a native
    model library costs the effect, not the edit.
    """

    def __init__(self, process: subprocess.Popen | None, result: pathlib.Path,
                 log: pathlib.Path, started: float, reason: str = "") -> None:
        self._process, self._result, self._log = process, result, log
        self.started = started
        self.reason = reason
        self.seconds = 0.0   # how long separating took
        self.waited = 0.0    # how long the caller was held up by it

    @classmethod
    def start(cls, takes: list[str], out_dir: str | pathlib.Path) -> "Matting":
        out_dir = pathlib.Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        result, log = out_dir / "mattes.json", out_dir / "matting.log"
        result.unlink(missing_ok=True)
        if os.environ.get("HALFHEAVEN_MATTE", "").lower() in ("0", "off", "false"):
            return cls(None, result, log, time.monotonic(), "turned off")
        with log.open("w") as sink:
            process = subprocess.Popen(
                [sys.executable, "-m", "halfheaven.analyze.matte", *takes,
                 "--out", str(out_dir), "--result", str(result)],
                stdout=sink, stderr=subprocess.STDOUT,
            )
        # A pipeline that stops early must not leave a GPU job running behind it.
        atexit.register(lambda: process.poll() is None and process.kill())
        return cls(process, result, log, time.monotonic())

    def result(self) -> dict[str, TakeMatte] | None:
        """The mattes, or None with `reason` saying why there are none."""
        if self._process is None:
            return None
        asked = time.monotonic()
        code = self._process.wait()
        self.waited = time.monotonic() - asked
        self.seconds = time.monotonic() - self.started
        lines = [line for line in self._log.read_text().splitlines() if line.strip()]
        for line in lines:
            if line.startswith("matted ") and line.endswith("s"):
                self.seconds = float(line.rsplit(" ", 1)[-1][:-1])
        if code != 0 or not self._result.exists():
            self.reason = lines[-1] if lines else f"exited {code}"
            return None
        return {take: TakeMatte(**matte)
                for take, matte in json.loads(self._result.read_text()).items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write subject and skin mattes for takes.")
    parser.add_argument("takes", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--result", help="write the mattes as JSON here")
    args = parser.parse_args(argv)
    started = time.monotonic()
    mattes = matte_takes(args.takes, args.out)
    payload = {take: matte.model_dump() for take, matte in mattes.items()}
    if args.result:
        partial = pathlib.Path(args.result).with_suffix(".part")
        partial.write_text(json.dumps(payload, indent=2))
        partial.rename(args.result)
    else:
        print(json.dumps(payload, indent=2))
    print(f"matted {len(mattes)} take(s) in {time.monotonic() - started:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
