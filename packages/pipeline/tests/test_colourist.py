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
    assert 0.85 <= controls.skin_chroma <= 2.0
    assert -4.0 <= controls.face_lift <= 8.0
    assert abs(controls.white_balance_deg) <= 12.0 * 0.8 + 1e-6


def test_white_balance_turns_skin_only_part_of_the_way():
    take = make_look(skin_ab=(10.0, 17.32))     # hue 60 degrees
    ref = make_look(skin_ab=(-17.32, 10.0))     # hue 150 degrees
    controls = plan_grade(take, ref, 1.0)
    assert controls.white_balance_deg == pytest.approx(9.6, abs=0.01)
    turned = apply_controls(np.array([[[45.0, 10.0, 17.32]]], np.float32), controls, "skin")[0, 0]
    assert np.degrees(np.arctan2(turned[2], turned[1])) == pytest.approx(69.6, abs=1.5)


def test_the_room_is_crushed_while_the_face_follows_the_references():
    take = make_look(subject_l=55.0, background_l=55.0, skin_l=40.0)
    ref = make_look(subject_l=30.0, background_l=9.0, skin_l=45.0)
    controls = plan_grade(take, ref, 1.0)
    skin = np.array([[[40.0, 14.0, 16.0]]], np.float32)
    wall = np.array([[[55.0, 2.0, 6.0]]], np.float32)
    assert apply_controls(skin, controls, "skin")[0, 0, 0] == pytest.approx(45.0, abs=1e-3)
    assert apply_controls(wall, controls, "background")[0, 0, 0] < 25.0


def test_a_bright_shirt_does_not_set_the_faces_level():
    # A bright shirt lifts the subject zone's median well above the face; the
    # subject's curve still takes the face exactly where the skin goes, since
    # the skin matte may only partly cover it.
    take = make_look(subject_l=60.0, skin_l=40.0)
    ref = make_look(subject_l=25.0, skin_l=45.0)
    controls = plan_grade(take, ref, 1.0)
    face = np.array([[[40.0, 14.0, 16.0]]], np.float32)
    shirt = np.array([[[85.0, 2.0, -8.0]]], np.float32)
    assert apply_controls(face, controls, "subject")[0, 0, 0] == pytest.approx(45.0, abs=0.5)
    # Lit with the face, the shirt brightens no further than the face does.
    assert apply_controls(shirt, controls, "subject")[0, 0, 0] <= 85.0 + 5.0 + 0.5


def test_a_daylit_reference_does_not_wash_out_a_dim_room():
    # The Day 3 reel's background is a bright sky; its level is content, not
    # grade. Lifting a dim room up to it turned the blacks milky (L 0 -> 67).
    take = make_look(subject_l=35.0, background_l=21.0, skin_l=40.0)
    ref = make_look(subject_l=60.0, background_l=68.0, skin_l=20.0)
    controls = plan_grade(take, ref, 1.0)
    for zone in ("subject", "background"):
        for lightness in (0.0, 10.0, 21.0):
            pixel = np.array([[[lightness, 0.0, 0.0]]], np.float32)
            assert apply_controls(pixel, controls, zone)[0, 0, 0] <= lightness + 12.0 + 1e-3


def test_a_take_with_no_skin_in_view_gets_no_skin_moves():
    controls = plan_grade(make_look(skin=False), make_look(skin_ab=(25.0, 10.0)), 1.0)
    assert controls.white_balance_ab == (0.0, 0.0)
    assert controls.exposure_anchor == 1.0 and controls.skin_chroma == 1.0
    assert controls.face_lift == 0.0
    assert np.isfinite(apply_controls(PIXELS, controls, "skin")).all()


def _hue(pixel):
    return float(np.degrees(np.arctan2(pixel[2], pixel[1])))


def test_the_subjects_own_colours_are_not_read_as_a_tint():
    # The day 4 reel's near-neutral subject pixels are a blue-grey shirt. Read
    # as a split tone, they turned the creator's skin pink (hue 32 -> 21) and a
    # grey jumper blue.
    take = make_look(skin_ab=(13.7, 8.5))
    ref = make_look(skin_ab=(13.7, 8.5), subject_tint=(1.0, -8.0))
    controls = plan_grade(take, ref, 1.0)
    skin = apply_controls(np.array([[[36.0, 13.7, 8.5]]], np.float32), controls, "skin")[0, 0]
    grey = apply_controls(np.array([[[40.0, 0.0, 0.0]]], np.float32), controls, "subject")[0, 0]
    assert _hue(skin) == pytest.approx(31.8, abs=1.0)
    assert abs(grey[1]) < 0.5 and abs(grey[2]) < 0.5


def test_the_rooms_tint_reaches_the_subjects_greys_but_not_the_skin():
    take = make_look(skin_ab=(13.7, 8.5))
    ref = make_look(skin_ab=(13.7, 8.5), background_tint=(6.0, 0.0))
    controls = plan_grade(take, ref, 1.0)
    grey = apply_controls(np.array([[[40.0, 0.0, 0.0]]], np.float32), controls, "subject")[0, 0]
    skin = apply_controls(np.array([[[36.0, 13.7, 8.5]]], np.float32), controls, "skin")[0, 0]
    assert grey[1] == pytest.approx(6.0, abs=0.5)
    assert _hue(skin) == pytest.approx(31.8, abs=1.0)


def test_skin_grows_as_rich_as_the_references():
    # The day 4 reel's skin is nearly twice as rich as the take's, at the same hue.
    take = make_look(skin_ab=(13.7, 8.5))       # chroma 16.1
    ref = make_look(skin_ab=(25.8, 16.3))       # chroma 30.5
    controls = plan_grade(take, ref, 1.0)
    skin = apply_controls(np.array([[[36.0, 13.7, 8.5]]], np.float32), controls, "skin")[0, 0]
    assert float(np.hypot(skin[1], skin[2])) == pytest.approx(30.5, abs=1.0)


@pytest.mark.parametrize("take_face, ref_face, graded_face", [
    (36.0, 46.0, 44.0),     # brighter, by at most 8 L
    (40.0, 45.0, 45.0),     # all the way when it is near
    (40.0, 20.0, 36.0),     # darker, by at most 4 L: more turned faces muddy
])
def test_the_face_moves_toward_the_references_face_within_bounds(take_face, ref_face, graded_face):
    controls = plan_grade(make_look(skin_l=take_face), make_look(skin_l=ref_face), 1.0)
    face = np.array([[[take_face, 14.0, 16.0]]], np.float32)
    assert apply_controls(face, controls, "skin")[0, 0, 0] == pytest.approx(graded_face, abs=1e-3)
    # The subject's curve takes the face to the same place, or the skin matte's edge shows.
    assert apply_controls(face, controls, "subject")[0, 0, 0] == pytest.approx(graded_face, abs=0.5)


def test_the_subject_keeps_its_blacks():
    # Pivoting the subject's curve on the face lifted the whole curve with it:
    # hair and clothes went from L 3 to 11 while the reference keeps them at 5.
    take = make_look(subject_l=50.0, skin_l=36.0)
    ref = make_look(subject_l=45.0, skin_l=46.0)
    controls = plan_grade(take, ref, 1.0)
    for lightness, most in ((0.0, 2.0), (3.0, 5.0)):
        pixel = np.array([[[lightness, 0.0, 0.0]]], np.float32)
        assert apply_controls(pixel, controls, "subject")[0, 0, 0] <= most
