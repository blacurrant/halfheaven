"""The reference's grade, read per zone, and carried into the style profile."""
from halfheaven.analyze.fingerprint import Confidence, FrameStats, _grade_zones
from halfheaven.plan.typography import apply_fingerprint
from halfheaven.schemas import StyleProfile, ZoneLook
from tests.zone_fakes import WIDE, ellipse_parts


def photo(t):
    return FrameStats(t=t, mean_rgb=(0.0, 0.0, 0.0), modal_share=0.1, graphic=False, text_area=0.0,
                      text_centroid=None, text_bbox=None, accent_share=0.0, glyph_height=0.0,
                      stroke_width=0.0, stroke_modulation=0.0, slant=0.0, motion=0.0, zoom=1.0)


def test_the_grade_reads_the_face_against_the_room():
    readings, look = _grade_zones(WIDE, [photo(0.1 + 0.3 * i) for i in range(14)], parts=ellipse_parts)
    assert readings["face_above_background"].value > 45
    assert readings["skin_hue"].confidence is Confidence.MEASURED
    assert isinstance(look, ZoneLook) and len(look.subject.l_quantiles) == 101


def test_without_enough_photography_the_zone_readings_are_absent():
    readings, look = _grade_zones(WIDE, [photo(0.5)] * 3, parts=ellipse_parts)
    assert look is None
    assert all(r.confidence is Confidence.ABSENT for r in readings.values())


def test_the_profile_carries_the_reference_zones():
    _, look = _grade_zones(WIDE, [photo(0.1 + 0.3 * i) for i in range(14)], parts=ellipse_parts)
    reading = lambda value: {"value": value, "confidence": "measured", "note": ""}
    fingerprint = {"grade": {"lab_mean": reading([30.0, 4.0, 6.0]), "lab_std": reading([15.0, 8.0, 9.0])},
                   "zone_look": look.model_dump()}
    profile = apply_fingerprint(StyleProfile(), fingerprint)
    assert profile.grade.zones == look


def test_a_profile_without_zones_keeps_none():
    reading = lambda value: {"value": value, "confidence": "measured", "note": ""}
    fingerprint = {"grade": {"lab_mean": reading([30.0, 4.0, 6.0]), "lab_std": reading([15.0, 8.0, 9.0])}}
    assert apply_fingerprint(StyleProfile(), fingerprint).grade.zones is None
