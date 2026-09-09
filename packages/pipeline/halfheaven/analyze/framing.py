"""Letterbox detection.

A strong, cheap style signal - putting the content in a band with black bars is
a deliberate look. It is also a prerequisite for measuring the grade: colour
statistics sampled through the bars would drag the whole transfer dark.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

import cv2
import numpy as np

# A bar row is near-black and near-uniform across the whole row.
BAR_LUMA = 24
BAR_UNIFORMITY = 10
# Bars must persist across sampled frames; a single dark shot is not a bar.
BAR_AGREEMENT = 0.8
MIN_BAR_PCT = 0.02
SAMPLES = 12


@dataclass(frozen=True)
class Framing:
    top_pct: float
    bottom_pct: float

    @property
    def is_letterboxed(self) -> bool:
        return self.top_pct > 0.0 or self.bottom_pct > 0.0

    def content_rows(self, frame_height: int) -> tuple[int, int]:
        """First and last-plus-one row of actual picture."""
        return (
            int(round(self.top_pct * frame_height)),
            frame_height - int(round(self.bottom_pct * frame_height)),
        )


def _bar_depth(gray: np.ndarray) -> tuple[int, int]:
    """Rows of black bar at the top and bottom of one frame."""
    dark = (gray.mean(axis=1) <= BAR_LUMA) & (gray.std(axis=1) <= BAR_UNIFORMITY)
    height = len(dark)

    top = 0
    while top < height and dark[top]:
        top += 1
    bottom = 0
    while bottom < height and dark[height - 1 - bottom]:
        bottom += 1
    # An entirely black frame is a fade, not a letterbox.
    return (0, 0) if top + bottom >= height else (top, bottom)


def detect_letterbox(video: str | pathlib.Path, samples: int = SAMPLES) -> Framing:
    capture = cv2.VideoCapture(str(video))
    try:
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1
        tops: list[int] = []
        bottoms: list[int] = []
        for index in range(samples):
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(total * (index + 0.5) / samples))
            ok, frame = capture.read()
            if not ok:
                continue
            top, bottom = _bar_depth(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            tops.append(top)
            bottoms.append(bottom)
    finally:
        capture.release()

    if not tops:
        return Framing(0.0, 0.0)

    def agreed(depths: list[int]) -> float:
        # The depth at least BAR_AGREEMENT of frames reach: a bar is structural,
        # so it is present in nearly every frame, and the odd dark shot cannot
        # invent one.
        ordered = sorted(depths)
        depth = ordered[int((1.0 - BAR_AGREEMENT) * (len(ordered) - 1))]
        pct = depth / height
        return pct if pct >= MIN_BAR_PCT else 0.0

    return Framing(top_pct=round(agreed(tops), 4), bottom_pct=round(agreed(bottoms), 4))
