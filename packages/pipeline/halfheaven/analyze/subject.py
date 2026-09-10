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

import pathlib
from dataclasses import dataclass
from typing import Sequence

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
    video: str | pathlib.Path, samples: int = SAMPLES
) -> SubjectPrompt:
    video = pathlib.Path(video)
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
) -> list[float]:
    """Where the subject sits during each span, as a fraction of frame width.

    Motion is the signal, as it is for a single prompt: the speaker moves and
    the room does not. Each result is pulled back toward centre, because
    background movement and compression also register and a crop that swings to
    the edge reads as a mistake. Deterministic, so the same footage reframes the
    same way twice.
    """
    video = pathlib.Path(video)
    if not spans:
        return []

    capture = cv2.VideoCapture(str(video))
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1
        track: list[float] = []

        for start, end in spans:
            frames: list[np.ndarray] = []
            for index in range(samples):
                at = start + (end - start) * (index + 0.5) / samples
                capture.set(cv2.CAP_PROP_POS_FRAMES, int(at * fps))
                ok, frame = capture.read()
                if ok:
                    frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32))

            energy = _column_energy(frames)
            centre = 0.5
            if energy is not None and energy.max() > MOTION_THRESHOLD * energy.mean():
                weights = np.clip(energy - energy.mean(), 0, None)
                if weights.sum() > 0:
                    centre = float((np.arange(width) * weights).sum() / weights.sum() / width)
            track.append(round(float(np.clip(centre, 0.5 - TRACK_LIMIT, 0.5 + TRACK_LIMIT)), 4))
        return track
    finally:
        capture.release()
