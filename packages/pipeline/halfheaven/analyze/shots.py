"""Shot boundary detection and the pacing profile derived from it.

Pacing is the highest-confidence signal we can recover from a rendered video,
and it needs no audio - which is why it is the backbone of the StyleProfile.
"""
from __future__ import annotations

import contextlib
import functools
import pathlib
import statistics
import subprocess
import sys
from dataclasses import dataclass

import numpy as np
from scenedetect import ContentDetector, detect

from halfheaven.media.ffmpeg_bin import ffmpeg
from halfheaven.media.probe import probe

DEFAULT_THRESHOLD = 27.0


@dataclass(frozen=True)
class Shot:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class Pacing:
    shot_count: int
    median_shot: float
    p10_shot: float
    p90_shot: float
    cuts_per_min: float
    total_duration: float


def detect_shots(path: str | pathlib.Path, threshold: float = DEFAULT_THRESHOLD) -> list[Shot]:
    """Shot list for a video. Always at least one shot.

    scenedetect returns an empty list for a video it finds no cuts in. That is
    not the same as "no shots" - a continuous take is one shot - and downstream
    pacing maths divides by the count, so we normalise here.
    """
    path = pathlib.Path(path).resolve()
    # One render asks for the reference's shots twice (the style profile, then
    # the caption band), and the learned detector costs a third of real time.
    return list(_detect_shots(path, path.stat().st_mtime_ns, threshold))


@functools.lru_cache(maxsize=16)
def _detect_shots(path: pathlib.Path, _mtime: int, threshold: float) -> tuple[Shot, ...]:
    info = probe(path)
    duration = info.duration
    learned = _transnet_shots(path, duration, info.fps)
    if learned is not None:
        return tuple(learned)
    scenes = detect(str(path), ContentDetector(threshold=threshold))
    if not scenes:
        return (Shot(start=0.0, end=duration),)
    return tuple(Shot(start=start.seconds, end=end.seconds) for start, end in scenes)


@functools.cache
def _transnet():
    from transnetv2_pytorch import TransNetV2
    import torch
    # CPU on purpose: MPS lacks avg_pool3d, and the port warns it drifts anyway.
    # Loading it turns on deterministic mode for the whole process; put it back
    # so the aligner and beat tracker run as they would without it.
    deterministic = torch.are_deterministic_algorithms_enabled()
    model = TransNetV2(device="cpu")
    torch.use_deterministic_algorithms(deterministic)
    return model


def _transnet_shots(path: pathlib.Path, duration: float, fps: float) -> list[Shot] | None:
    """Shots from TransNetV2, or None when it is not installed or fails.

    A colour-difference detector sees a hard cut and misses a dissolve, whose
    frames each differ only a little from the last. TransNetV2 was trained on
    both. A gradual transition belongs to neither shot, so its cut is placed at
    the middle of it.
    """
    try:
        import torch
        from transnetv2_pytorch import TransNetV2
    except ImportError:
        return None
    try:
        raw = subprocess.run(
            [ffmpeg(), "-v", "error", "-i", str(path), "-f", "rawvideo",
             "-pix_fmt", "rgb24", "-s", "48x27", "pipe:"],
            check=True, capture_output=True).stdout
        frames = torch.from_numpy(np.frombuffer(raw, np.uint8).reshape(-1, 27, 48, 3).copy())
        # Library chatter goes to stderr: the fingerprint CLI's stdout is JSON.
        with contextlib.redirect_stdout(sys.stderr):
            single, _ = _transnet().predict_frames(frames, quiet=True)
        scenes = TransNetV2.predictions_to_scenes(single.numpy())
        rate = fps or len(frames) / duration
    except Exception as error:
        print(f"TransNetV2 failed, using scenedetect: {error}", file=sys.stderr)
        return None
    cuts = [float(previous[1] + 1 + scene[0]) / 2 / rate for previous, scene in zip(scenes, scenes[1:])]
    edges = [0.0, *cuts, duration]
    return [Shot(start=a, end=b) for a, b in zip(edges, edges[1:])]


def pacing(shots: list[Shot]) -> Pacing:
    durations = sorted(s.duration for s in shots)
    total = sum(durations)
    cuts = max(0, len(shots) - 1)
    return Pacing(
        shot_count=len(shots),
        median_shot=statistics.median(durations) if durations else 0.0,
        p10_shot=_percentile(durations, 0.10),
        p90_shot=_percentile(durations, 0.90),
        cuts_per_min=(60.0 * cuts / total) if total else 0.0,
        total_duration=total,
    )


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    index = fraction * (len(sorted_values) - 1)
    low = int(index)
    high = min(low + 1, len(sorted_values) - 1)
    weight = index - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight
