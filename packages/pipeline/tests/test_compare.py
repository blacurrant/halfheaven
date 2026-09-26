"""The scorecard's zone traits."""
from types import SimpleNamespace

from halfheaven.analyze.compare import Verdict, _angle, compare
from halfheaven.analyze.fingerprint import Reading


def grade_only(source, **values):
    readings = {name: (Reading.absent("none") if value is None else Reading(value))
                for name, value in values.items()}
    return SimpleNamespace(source=source, grade=SimpleNamespace(**readings))


def rows_by_field(card):
    return {row.trait.field: row for row in card.rows if row.trait.group == "grade"}


def test_hue_distance_wraps_round_the_circle():
    assert _angle(350.0, 10.0) == 20.0
    assert _angle(-170.0, 170.0) == 20.0


def test_close_zone_readings_match_and_far_ones_miss():
    ours = grade_only("out", face_above_background=20.0, background_l=14.0, skin_chroma=28.0,
                      skin_hue=43.5, shadow_tint=8.2)
    theirs = grade_only("ref", face_above_background=28.8, background_l=8.9, skin_chroma=29.8,
                        skin_hue=31.9, shadow_tint=7.1)
    rows = rows_by_field(compare(ours, theirs))
    assert rows["background_l"].verdict is Verdict.MATCH          # 5.1 <= 6
    assert rows["face_above_background"].verdict is Verdict.NEAR  # 8.8 <= 12
    assert rows["skin_chroma"].verdict is Verdict.MATCH
    assert rows["skin_hue"].verdict is Verdict.NEAR               # 11.6 <= 12
    assert rows["shadow_tint"].verdict is Verdict.MATCH


def test_a_zone_reading_missing_on_either_side_is_unscored():
    ours = grade_only("out", face_above_background=None, background_l=14.0, skin_chroma=None,
                      skin_hue=None, shadow_tint=None)
    theirs = grade_only("ref", face_above_background=28.8, background_l=None, skin_chroma=29.8,
                        skin_hue=31.9, shadow_tint=7.1)
    rows = rows_by_field(compare(ours, theirs))
    assert all(rows[f].verdict is Verdict.UNSCORED
               for f in ("face_above_background", "background_l", "skin_chroma", "skin_hue", "shadow_tint"))
