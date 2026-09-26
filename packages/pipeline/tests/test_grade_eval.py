"""Measuring what a grade does at the matte edge and over time."""
import numpy as np
import pytest

from halfheaven.analyze.grade_eval import flicker, seam


def edge_scene():
    lightness = np.full((568, 100), 20.0, np.float32)
    lightness[:, :50] = 60.0
    alpha = np.zeros((568, 100), np.float32)
    alpha[:, :50] = 1.0
    return lightness, alpha


def test_a_clean_edge_has_no_seam():
    lightness, alpha = edge_scene()
    assert seam(lightness, alpha) == pytest.approx(0.0, abs=0.5)


def test_a_bright_rim_reads_positive_and_a_dark_line_negative():
    lightness, alpha = edge_scene()
    rim, line = lightness.copy(), lightness.copy()
    rim[:, 50:52] = 90.0         # just outside the subject: a glow on the wall
    line[:, 48:50] = 0.0         # just inside: a dark outline on the hair
    assert seam(rim, alpha) > 3.0
    assert seam(line, alpha) < -3.0


def test_flicker_is_what_the_grade_adds_over_the_footage():
    raw = [np.full((60, 60), 30.0, np.float32) for _ in range(6)]
    steady = [frame.copy() for frame in raw]
    pumping = [frame + (3.0 if k % 2 else 0.0) for k, frame in enumerate(raw)]
    alphas = [np.zeros((60, 60), np.float32)] * 6
    skins = [np.zeros((60, 60), np.float32)] * 6
    assert flicker(steady, raw, alphas, skins)["room"] == pytest.approx(0.0)
    assert flicker(pumping, raw, alphas, skins)["room"] == pytest.approx(3.0)
    assert flicker(steady, raw, alphas, skins)["face"] is None
