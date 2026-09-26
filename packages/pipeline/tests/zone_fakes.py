"""Stand-ins shared by the zone-grade tests: fixtures, fake models, synthetic looks."""
import pathlib

import numpy as np

from halfheaven.analyze.matte import BACKGROUND, FACE_SKIN

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
# 640x360, 25fps, 4.4s: a skin-coloured ellipse (228,196,172) on a dark, near-neutral room.
WIDE = FIXTURES / "wide_subject_moves.mp4"
BARS = FIXTURES / "three_shots_at_1.0_3.0.mp4"      # 320x568, 4.5s


class Bright:
    """Segmenter stand-in: the wide fixture's subject is the only bright thing in it."""

    def mask_for(self, frame):
        return np.where(frame.max(axis=2) > 150, 255, 0).astype(np.uint8)


def ellipse_parts(rgb, t_ms):
    """MediaPipe stand-in: the bright ellipse is a person, all of it face skin."""
    return np.where(rgb.max(axis=2) > 150, FACE_SKIN, BACKGROUND).astype(np.uint8)


def tiny_parts(rgb, t_ms):
    """MediaPipe stand-in: a person far too small to read a grade from."""
    classes = np.full(rgb.shape[:2], BACKGROUND, np.uint8)
    classes[:10, :10] = FACE_SKIN
    return classes
