"""Colour transfer as a baked 3D LUT.

The reference's look is matched statistically in LAB - mean and spread per
channel - and baked into a .cube that ffmpeg's lut3d applies in one pass. We
are matching an appearance, not recovering the reference's original transform,
so no ungraded source is needed.
"""
import pytest

from halfheaven.render.lut import ColorStats, write_lut

NEUTRAL = ColorStats(mean=(50.0, 0.0, 0.0), std=(20.0, 10.0, 10.0))
WARM_DARK = ColorStats(mean=(30.0, 8.0, 18.0), std=(18.0, 9.0, 12.0))


def read_cube(path):
    size = None
    entries = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("LUT_3D_SIZE"):
            size = int(line.split()[1])
        elif line and not line[0].isalpha() and not line.startswith("#"):
            entries.append(tuple(float(v) for v in line.split()))
    return size, entries


def sample(entries, size, rgb):
    """Nearest grid entry for an RGB triple in 0-1. Cube order is R fastest."""
    r, g, b = (min(size - 1, round(c * (size - 1))) for c in rgb)
    return entries[r + g * size + b * size * size]


def test_writes_a_cube_with_the_declared_size(tmp_path):
    path = write_lut(NEUTRAL, WARM_DARK, tmp_path / "g.cube", size=17)
    size, entries = read_cube(path)
    assert size == 17 and len(entries) == 17 ** 3


def test_all_entries_stay_inside_the_unit_range(tmp_path):
    _, entries = read_cube(write_lut(NEUTRAL, WARM_DARK, tmp_path / "g.cube", size=17))
    assert all(0.0 <= channel <= 1.0 for entry in entries for channel in entry)


def test_matching_source_and_target_is_an_identity_transform(tmp_path):
    size, entries = read_cube(write_lut(NEUTRAL, NEUTRAL, tmp_path / "g.cube", size=17))
    for probe in [(0.25, 0.25, 0.25), (0.5, 0.5, 0.5), (0.75, 0.5, 0.25)]:
        assert sample(entries, size, probe) == pytest.approx(probe, abs=0.03)


def test_zero_strength_is_an_identity_transform(tmp_path):
    size, entries = read_cube(write_lut(NEUTRAL, WARM_DARK, tmp_path / "g.cube", size=17, strength=0.0))
    assert sample(entries, size, (0.5, 0.5, 0.5)) == pytest.approx((0.5, 0.5, 0.5), abs=0.03)


def test_a_darker_target_darkens_mid_grey(tmp_path):
    size, entries = read_cube(write_lut(NEUTRAL, WARM_DARK, tmp_path / "g.cube", size=17))
    red, green, blue = sample(entries, size, (0.5, 0.5, 0.5))
    assert (red + green + blue) / 3 < 0.5


def test_a_warm_target_pushes_mid_grey_warm(tmp_path):
    size, entries = read_cube(write_lut(NEUTRAL, WARM_DARK, tmp_path / "g.cube", size=17))
    red, green, blue = sample(entries, size, (0.5, 0.5, 0.5))
    assert red > blue


def test_strength_scales_the_effect(tmp_path):
    size, full = read_cube(write_lut(NEUTRAL, WARM_DARK, tmp_path / "f.cube", size=17))
    _, half = read_cube(write_lut(NEUTRAL, WARM_DARK, tmp_path / "h.cube", size=17, strength=0.5))
    grey = (0.5, 0.5, 0.5)
    full_shift = abs(sum(sample(full, size, grey)) / 3 - 0.5)
    half_shift = abs(sum(sample(half, size, grey)) / 3 - 0.5)
    assert half_shift < full_shift


import cv2
import numpy as np

from halfheaven.plan.colourist import plan_grade
from halfheaven.render.lut import write_zone_luts
from tests.zone_fakes import make_look


def entry(entries, size, r, g, b):
    return np.array(entries[r + g * size + b * size * size], np.float32)


def lightness(rgb):
    return float(cv2.cvtColor(np.array([[rgb]], np.float32), cv2.COLOR_RGB2LAB)[0, 0, 0])


def test_zone_luts_at_zero_strength_are_identities(tmp_path):
    controls = plan_grade(make_look(background_l=55.0), make_look(background_l=9.0), 0.0)
    for zone, path in write_zone_luts(controls, tmp_path, size=17).items():
        size, entries = read_cube(path)
        assert size == 17 and len(entries) == 17 ** 3
        for index in [(3, 5, 7), (8, 8, 8), (15, 10, 5)]:
            expected = np.array(index, np.float32) / (size - 1)
            assert np.abs(entry(entries, size, *index) - expected).max() < 1 / 255, zone


def test_the_skin_lut_keeps_skin_brightness_while_the_subject_lut_darkens_the_rest(tmp_path):
    controls = plan_grade(make_look(subject_l=55.0, skin_l=40.0), make_look(subject_l=20.0, skin_l=45.0), 1.0)
    paths = write_zone_luts(controls, tmp_path, size=17)
    _, skin = read_cube(paths["skin"])
    _, subject = read_cube(paths["subject"])
    for index in [(10, 7, 5), (12, 9, 8), (6, 4, 3)]:            # skin-like colours
        source = lightness(np.array(index, np.float32) / 16)
        assert lightness(entry(skin, 17, *index)) == pytest.approx(source, abs=1.0)
    shirt = (14, 14, 15)                                          # a pale shirt, far above the face
    assert lightness(entry(subject, 17, *shirt)) < lightness(np.array(shirt, np.float32) / 16) - 5
