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


from halfheaven.schemas import SkinTone, ZoneLook, ZoneTone


def make_tone(center, spread=50.0, chroma=8.0, tint=(0.0, 0.0), shadow_a=None):
    """A zone whose L runs evenly from center-spread to center+spread, clipped to 0..100."""
    quantiles = np.clip(np.linspace(center - spread, center + spread, 101), 0.0, 100.0)
    return ZoneTone(l_quantiles=[float(v) for v in quantiles], mean_l=float(quantiles.mean()),
                    median_chroma=chroma, tints=[tuple(tint)] * 6, shadow_tint_a=shadow_a)


def make_look(subject_l=50.0, background_l=50.0, skin_l=45.0, skin_ab=(14.0, 16.0),
              subject_chroma=8.0, background_chroma=8.0, background_tint=(0.0, 0.0), skin=True):
    return ZoneLook(
        subject=make_tone(subject_l, chroma=subject_chroma),
        background=make_tone(background_l, chroma=background_chroma, tint=background_tint),
        skin=SkinTone(ab=skin_ab, mean_l=skin_l, median_l=skin_l) if skin else None,
    )


from PIL import Image

from halfheaven.render.lut import ColorStats, write_lut

_NEUTRAL = ColorStats(mean=(50.0, 0.0, 0.0), std=(20.0, 10.0, 10.0))


class LeftHalf:
    def mask_for(self, frame):
        mask = np.zeros(frame.shape[:2], np.uint8)
        mask[:, : frame.shape[1] // 2] = 255
        return mask


class Nothing:
    def mask_for(self, frame):
        return np.zeros(frame.shape[:2], np.uint8)


def identity_lut(path):
    return write_lut(_NEUTRAL, _NEUTRAL, path, size=17)


def dark_lut(path):
    return write_lut(ColorStats(mean=(60.0, 0.0, 0.0), std=(20.0, 10.0, 10.0)),
                     ColorStats(mean=(25.0, 0.0, 0.0), std=(12.0, 10.0, 10.0)), path, size=17)


def gray(image_or_path):
    image = image_or_path if isinstance(image_or_path, Image.Image) else Image.open(image_or_path)
    return np.array(image.convert("L")).astype(int)
