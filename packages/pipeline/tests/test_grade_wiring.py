"""Which grade a render gets, and what it is baked from."""
import json
import pathlib

from halfheaven.analyze.segment import write_matte_video
from halfheaven.plan.grade import describe_controls, global_lut_for, zone_grade_for
from halfheaven.schemas import GradeProfile, StyleProfile, TakeMatte
from tests.zone_fakes import WIDE, Bright, make_look


def zoned_profile(**grade):
    return StyleProfile(grade=GradeProfile(measured=True, zones=make_look(background_l=40.0), **grade))


def ellipse_mattes(tmp_path, skin=True):
    matte = write_matte_video(WIDE, Bright(), tmp_path / "m.mp4", feather=0)
    return {str(WIDE): TakeMatte(subject=str(matte), skin=str(matte) if skin else None)}


def test_the_colourist_grade_is_made_when_everything_is_there(tmp_path):
    profile = zoned_profile()
    grade = zone_grade_for(profile, [str(WIDE)], ellipse_mattes(tmp_path), tmp_path)
    assert grade is not None
    assert all(pathlib.Path(p).exists() for p in (grade.subject_lut, grade.background_lut, grade.skin_lut))
    assert grade.controls.strength == profile.grade.strength
    assert "white balance" in describe_controls(grade.controls)


def test_no_zones_means_no_colourist_grade(tmp_path):
    profile = StyleProfile(grade=GradeProfile(measured=True))
    assert zone_grade_for(profile, [str(WIDE)], ellipse_mattes(tmp_path), tmp_path) is None


def test_a_take_without_a_skin_matte_keeps_the_single_grade(tmp_path):
    assert zone_grade_for(zoned_profile(), [str(WIDE)], ellipse_mattes(tmp_path, skin=False), tmp_path) is None


def test_the_saved_profile_leaves_the_zone_table_out():
    # style_profile.json goes with every studio chat message: the zone table
    # was ~4,900 characters of floats, and a chat reply could null it.
    from halfheaven.cli import profile_json

    saved = json.loads(profile_json(zoned_profile()))
    assert "zones" not in saved["grade"]
    assert saved["grade"]["measured"] is True


def test_the_single_lut_is_baked_only_for_a_measured_reference(tmp_path):
    baked = global_lut_for(StyleProfile(grade=GradeProfile(measured=True)), [str(WIDE)], tmp_path)
    assert baked is not None and baked[0].exists()
    assert global_lut_for(StyleProfile(), [str(WIDE)], tmp_path) is None
