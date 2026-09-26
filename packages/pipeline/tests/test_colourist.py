"""A colourist's controls, read from a reference: bounded, and gentle with skin."""
import numpy as np
import pytest

from halfheaven.plan.colourist import GRID, apply_controls, plan_grade, tone_curve
from tests.zone_fakes import make_look, make_tone

ZONES = ("subject", "background", "skin")
_rng = np.random.default_rng(7)
PIXELS = np.stack([_rng.uniform(0, 100, 500), _rng.uniform(-40, 40, 500),
                   _rng.uniform(-40, 40, 500)], -1).astype(np.float32)[None]


def test_strength_zero_leaves_every_zone_untouched():
    controls = plan_grade(make_look(background_l=55.0), make_look(background_l=9.0, skin_ab=(25.0, 15.0)), 0.0)
    for zone in ZONES:
        assert np.abs(apply_controls(PIXELS, controls, zone) - PIXELS).max() < 1e-3


def test_matching_looks_barely_move_anything():
    look = make_look(subject_l=45.0, background_l=30.0)
    controls = plan_grade(look, look, 1.0)
    for zone in ("subject", "background"):
        assert np.abs(apply_controls(PIXELS, controls, zone) - PIXELS)[..., 0].mean() < 1.0


@pytest.mark.parametrize("reference", [
    make_tone(0.0, spread=0.0, chroma=0.0),       # a black reference
    make_tone(100.0, spread=0.0, chroma=0.0),     # a white one
    make_tone(9.0),                                # a crushed room, like the day 4 reel's
])
def test_curves_are_monotone_and_slope_limited(reference):
    curve = np.array(tone_curve(make_tone(55.0, spread=40.0).l_quantiles, reference.l_quantiles, 1.0))
    slope = np.diff(curve) / np.diff(GRID)
    assert (slope >= -1e-6).all()
    inside = (curve[:-1] > 0.0) & (curve[1:] < 100.0)
    assert slope[inside].max() <= 1.6 + 1e-6 and slope[inside].min() >= 0.12 - 1e-6


@pytest.mark.parametrize("reference", [
    make_look(subject_l=2.0, background_l=1.0, skin_l=5.0, skin_ab=(0.5, 0.5),
              subject_chroma=0.0, background_chroma=0.0),
    make_look(subject_l=98.0, background_l=99.0, skin_l=95.0, skin_ab=(60.0, -40.0),
              subject_chroma=90.0, background_chroma=90.0),
])
def test_no_reference_pushes_past_the_bounds(reference):
    controls = plan_grade(make_look(), reference, 1.0)
    assert 0.7 <= controls.exposure_anchor <= 1.5
    assert 0.85 <= controls.subject.saturation <= 1.15
    assert 0.8 <= controls.background.saturation <= 1.3
    assert 0.85 <= controls.skin_chroma <= 1.3
    assert abs(controls.white_balance_deg) <= 12.0 * 0.8 + 1e-6


def test_white_balance_turns_skin_only_part_of_the_way():
    take = make_look(skin_ab=(10.0, 17.32))     # hue 60 degrees
    ref = make_look(skin_ab=(-17.32, 10.0))     # hue 150 degrees
    controls = plan_grade(take, ref, 1.0)
    assert controls.white_balance_deg == pytest.approx(9.6, abs=0.01)
    turned = apply_controls(np.array([[[45.0, 10.0, 17.32]]], np.float32), controls, "skin")[0, 0]
    assert np.degrees(np.arctan2(turned[2], turned[1])) == pytest.approx(69.6, abs=1.5)


def test_skin_keeps_its_own_brightness_while_the_room_is_crushed():
    take = make_look(subject_l=55.0, background_l=55.0, skin_l=40.0)
    ref = make_look(subject_l=30.0, background_l=9.0, skin_l=45.0)
    controls = plan_grade(take, ref, 1.0)
    skin = np.array([[[40.0, 14.0, 16.0]]], np.float32)
    wall = np.array([[[55.0, 2.0, 6.0]]], np.float32)
    assert apply_controls(skin, controls, "skin")[0, 0, 0] == pytest.approx(40.0, abs=1e-3)
    assert apply_controls(wall, controls, "background")[0, 0, 0] < 25.0


def test_a_take_with_no_skin_in_view_gets_no_skin_moves():
    controls = plan_grade(make_look(skin=False), make_look(skin_ab=(25.0, 10.0)), 1.0)
    assert controls.white_balance_ab == (0.0, 0.0)
    assert controls.exposure_anchor == 1.0 and controls.skin_chroma == 1.0
    assert np.isfinite(apply_controls(PIXELS, controls, "skin")).all()
