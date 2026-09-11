"""Locating the speaker, to prompt a segmenter with.

SAM2 tracks whatever it is pointed at, so something has to point. A face
detector would be the obvious choice and is the wrong one: OpenCV's headless
build ships no cascades, and what we actually want is not a face but a person.

For a locked-off talking head the speaker is simply the thing that moves, so
temporal variance finds them with no model and no extra dependency. Where
nothing moves - a still frame, a tripod shot of an empty room - it falls back
to the centre column, which is where a subject sits in almost any short-form
composition.
"""
from __future__ import annotations

import functools
import pathlib
from dataclasses import dataclass
from typing import Protocol, Sequence

import cv2
import numpy as np

SAMPLES = 16
# Heights to place prompts at, as fractions of frame height: roughly face and
# chest. Two points rather than one, so the mask takes in the whole body
# instead of latching onto a head.
PROMPT_HEIGHTS = (0.34, 0.62)
# Motion must beat this multiple of the frame's average to count as a subject.
MOTION_THRESHOLD = 1.6
# How far motion may move the prompt from centre, as a fraction of width.
# Measured on real footage: in noedit.mp4 the motion centroid landed at x=0.80,
# on the plant and shelving behind a centred speaker. Background movement,
# camera noise and compression all register as motion, so motion gets a vote,
# not the decision. Short-form composition puts the subject near the centre.
MAX_NUDGE_PCT = 0.12


@dataclass(frozen=True)
class SubjectPrompt:
    points: list[tuple[int, int]]
    labels: list[int]  # 1 = foreground, in SAM's convention


def _sampled_frames(video: pathlib.Path, samples: int) -> list[np.ndarray]:
    capture = cv2.VideoCapture(str(video))
    try:
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        frames = []
        for index in range(samples):
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(total * index / samples))
            ok, frame = capture.read()
            if ok:
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32))
        return frames
    finally:
        capture.release()


def find_subject_prompt(
    video: str | pathlib.Path, samples: int = SAMPLES,
    detector: "FaceDetector | None" = None,
) -> SubjectPrompt:
    video = pathlib.Path(video)
    detector = detector if detector is not None else default_detector()
    # SAM2 is prompted on frame 0 and propagates from there, so the face that
    # matters is the one in frame 0. A face is a far better prompt than motion,
    # which on real footage has put this point on a plant behind the speaker.
    if detector is not None:
        capture = cv2.VideoCapture(str(video))
        try:
            ok, first = capture.read()
        finally:
            capture.release()
        face = _largest(detector.faces(first)) if ok else None
        if face is not None:
            height, width = first.shape[:2]
            x = int(np.clip(face.x * width, 1, width - 2))
            # face and chest, so the mask takes in the body and not only a head
            rows = (face.y, face.y + 1.6 * face.height)
            return SubjectPrompt(
                points=[(x, int(np.clip(r * height, 1, height - 2))) for r in rows],
                labels=[1, 1],
            )
    frames = _sampled_frames(video, samples)
    if not frames:
        raise ValueError(f"could not read frames from {video}")

    height, width = frames[0].shape
    centre_x = width // 2

    if len(frames) > 2:
        motion = np.stack(frames).std(axis=0)
        motion = cv2.GaussianBlur(motion, (31, 31), 0)
        column_energy = motion.sum(axis=0)
        # A scene where nothing moves gives a flat profile; picking its argmax
        # would be reading noise, so require a real peak first.
        if column_energy.max() > MOTION_THRESHOLD * column_energy.mean():
            weights = column_energy - column_energy.mean()
            weights[weights < 0] = 0
            if weights.sum() > 0:
                candidate = (np.arange(width) * weights).sum() / weights.sum()
                limit = width * MAX_NUDGE_PCT
                centre_x = int(np.clip(candidate, centre_x - limit, centre_x + limit))

    centre_x = int(np.clip(centre_x, 1, width - 2))
    points = [(centre_x, int(np.clip(height * f, 1, height - 2))) for f in PROMPT_HEIGHTS]
    return SubjectPrompt(points=points, labels=[1] * len(points))


# How far a tracked position may sit from centre. A subject is rarely pinned to
# the very edge, and an over-eager crop that swings to the frame border looks
# like a mistake rather than a camera move.
TRACK_LIMIT = 0.34
# Frames sampled per span. More is steadier and slower.
TRACK_SAMPLES = 5


def needs_reframe(info, canvas) -> bool:
    """True when the source is wider, relative to its height, than the canvas.

    Centre-cropping 16:9 into 9:16 discards two thirds of the width, so a
    speaker standing off to one side is simply cropped out. Knowing that in
    advance is what lets us follow them instead.
    """
    if not info.height or not canvas.height:
        return False
    return (info.width / info.height) > (canvas.width / canvas.height) * 1.05


def _column_energy(frames: list[np.ndarray]) -> np.ndarray | None:
    """Where the moving content is, column by column."""
    if len(frames) < 2:
        return None
    motion = np.stack(frames).std(axis=0)
    return cv2.GaussianBlur(motion, (31, 31), 0).sum(axis=0)


def track_subject(
    video: str | pathlib.Path,
    spans: Sequence[tuple[float, float]],
    samples: int = TRACK_SAMPLES,
    detector: "FaceDetector | None" = None,
) -> list[float]:
    """Where the subject sits during each span, as a fraction of frame width.

    The horizontal half of `locate_subject`, kept for callers that only move
    the crop sideways.
    """
    return [x for x, _ in locate_subject(video, spans, samples, detector)]


# --------------------------------------------------------------------------
# faces: the cheap, reliable half of subject recognition
# --------------------------------------------------------------------------

MODEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "assets" / "models"
FACE_MODEL = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
# Faces are found on a small copy of the frame. At 360 wide YuNet takes ~21ms
# and still finds a face a sixth of the frame tall.
FACE_WIDTH = 360
FACE_SCORE = 0.6
# The share of a span's samples that must show a face before it beats motion.
# A turned head or a blink should not throw a span away; a face seen once in
# five frames is as likely to be a poster on the wall.
FACE_QUORUM = 0.5
# Centre a little below the face, so it sits in the upper part of the frame the
# way an operator frames a speaker, rather than dead centre.
HEADROOM = 0.06


@dataclass(frozen=True)
class Face:
    x: float        # centre, fraction of frame width
    y: float        # centre, fraction of frame height
    height: float   # fraction of frame height
    score: float


class FaceDetector(Protocol):
    def faces(self, frame: np.ndarray) -> list[Face]:
        """Every face in one BGR frame, in frame-relative coordinates."""


class YuNetDetector:
    """OpenCV's DNN face detector. No new dependency: it ships in cv2, and its
    model is 232 KB in the repo."""

    def __init__(self, model: pathlib.Path = FACE_MODEL, width: int = FACE_WIDTH,
                 score: float = FACE_SCORE) -> None:
        self._model = str(model)
        self._width = width
        self._score = score
        self._net = None
        self._size: tuple[int, int] | None = None

    def faces(self, frame: np.ndarray) -> list[Face]:
        height = max(1, int(self._width * frame.shape[0] / frame.shape[1]))
        small = cv2.resize(frame, (self._width, height))
        if self._net is None:
            self._net = cv2.FaceDetectorYN.create(
                self._model, "", (self._width, height), self._score, 0.3, 20)
        if self._size != (self._width, height):
            self._net.setInputSize((self._width, height))
            self._size = (self._width, height)
        _, found = self._net.detect(small)
        if found is None:
            return []
        return [
            Face(x=float((row[0] + row[2] / 2) / self._width),
                 y=float((row[1] + row[3] / 2) / height),
                 height=float(row[3] / height), score=float(row[14]))
            for row in found
        ]


@functools.lru_cache(maxsize=1)
def default_detector() -> FaceDetector | None:
    """The shipped detector, or None when its model is missing - in which case
    everything falls back to motion rather than failing."""
    if not FACE_MODEL.exists():
        return None
    # The DNN backend warns about compute targets every time a detector is
    # created. OpenCV 5 moved the switch to cv2.utils.logging; the top-level
    # cv2.setLogLevel an earlier version of this called does not exist there,
    # and a blanket `except` hid that. So look for the API rather than catch.
    logging = getattr(getattr(cv2, "utils", None), "logging", None)
    if logging is not None and hasattr(logging, "setLogLevel"):
        logging.setLogLevel(logging.LOG_LEVEL_ERROR)
    return YuNetDetector()


def _largest(faces: list[Face]) -> Face | None:
    return max(faces, key=lambda face: face.height, default=None)


def locate_subject(
    video: str | pathlib.Path,
    spans: Sequence[tuple[float, float]],
    samples: int = TRACK_SAMPLES,
    detector: FaceDetector | None = None,
) -> list[tuple[float, float]]:
    """Where to centre the frame during each span, as (x, y) fractions.

    A face is the answer when there is one: it is where a viewer looks, and it
    costs ~21ms a frame against the ~740ms a segmenter needs - the difference
    between knowing where someone is and knowing which pixels they are. Motion
    is the fallback for a balaclava, a product shot or a turned back, and is
    pulled toward centre because background movement registers as well.
    Deterministic, so the same footage frames the same way twice.
    """
    video = pathlib.Path(video)
    if not spans:
        return []
    detector = detector if detector is not None else default_detector()

    capture = cv2.VideoCapture(str(video))
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1
        located: list[tuple[float, float]] = []
        for start, end in spans:
            frames = []
            for index in range(samples):
                at = start + (end - start) * (index + 0.5) / samples
                capture.set(cv2.CAP_PROP_POS_FRAMES, int(at * fps))
                ok, frame = capture.read()
                if ok:
                    frames.append(frame)

            faces = [_largest(detector.faces(f)) for f in frames] if detector else []
            faces = [face for face in faces if face is not None]
            if frames and len(faces) >= max(1, FACE_QUORUM * len(frames)):
                x = float(np.median([face.x for face in faces]))
                y = float(np.median([face.y for face in faces])) + HEADROOM
                located.append((round(float(np.clip(x, 0.05, 0.95)), 4),
                                round(float(np.clip(y, 0.05, 0.95)), 4)))
                continue

            gray = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames]
            energy = _column_energy(gray)
            centre = 0.5
            if energy is not None and energy.max() > MOTION_THRESHOLD * energy.mean():
                weights = np.clip(energy - energy.mean(), 0, None)
                if weights.sum() > 0:
                    centre = float((np.arange(width) * weights).sum() / weights.sum() / width)
            located.append(
                (round(float(np.clip(centre, 0.5 - TRACK_LIMIT, 0.5 + TRACK_LIMIT)), 4), 0.5))
        return located
    finally:
        capture.release()
