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
