"""The colourist grade, rendered: each zone takes its own LUT."""
import pytest

from halfheaven.analyze.segment import write_matte_video
from halfheaven.render.video import extract_frame, render
from halfheaven.schemas import Canvas, EditProgram, Look, TakeMatte, VideoClip, ZoneGrade
from tests.zone_fakes import BARS, LeftHalf, Nothing, dark_lut, gray, identity_lut

BASE = dict(canvas=Canvas(width=320, height=568, fps=30),
            video=[VideoClip(src=str(BARS), start=0.0, end=2.0)])


def halves(program, tmp_path, name):
    out = render(program, tmp_path / f"{name}.mp4", work_dir=tmp_path / name)
    frame = gray(extract_frame(out, 1.0, tmp_path / f"{name}.png"))
    return frame[:, 20:140].mean(), frame[:, 180:300].mean()


def mattes(tmp_path, skin_segmenter):
    left = write_matte_video(BARS, LeftHalf(), tmp_path / "left.mp4", feather=0)
    skin = write_matte_video(BARS, skin_segmenter, tmp_path / "skin.mp4", feather=0)
    return {str(BARS): TakeMatte(subject=str(left), skin=str(skin))}


def test_the_background_takes_its_own_grade_and_the_subject_keeps_its_own(tmp_path):
    grade = ZoneGrade(subject_lut=str(identity_lut(tmp_path / "i.cube")),
                      background_lut=str(dark_lut(tmp_path / "d.cube")),
                      skin_lut=str(identity_lut(tmp_path / "k.cube")))
    plain = halves(EditProgram(**BASE), tmp_path, "plain")
    zoned = halves(EditProgram(**BASE, look=Look(zone_grade=grade, mattes=mattes(tmp_path, Nothing()))),
                   tmp_path, "zoned")
    assert zoned[0] == pytest.approx(plain[0], abs=4), "the subject's LUT is the identity"
    assert zoned[1] < plain[1] - 10, "the background's LUT darkens"


def test_skin_keeps_its_brightness_when_the_subject_is_darkened(tmp_path):
    grade = ZoneGrade(subject_lut=str(dark_lut(tmp_path / "d.cube")),
                      background_lut=str(identity_lut(tmp_path / "i.cube")),
                      skin_lut=str(identity_lut(tmp_path / "k.cube")))
    plain = halves(EditProgram(**BASE), tmp_path, "plain")
    bare = halves(EditProgram(**BASE, look=Look(zone_grade=grade, mattes=mattes(tmp_path, Nothing()))),
                  tmp_path, "bare")
    assert bare[0] < plain[0] - 10, "with no skin in view the subject's LUT darkens"
    zoned = halves(EditProgram(**BASE, look=Look(zone_grade=grade, mattes=mattes(tmp_path, LeftHalf()))),
                   tmp_path, "zoned")
    assert zoned[0] == pytest.approx(plain[0], abs=10), "skin takes 90% of its own (identity) LUT"
    assert zoned[1] == pytest.approx(plain[1], abs=4)


def test_a_missing_matte_falls_back_to_the_single_lut(tmp_path):
    grade = ZoneGrade(subject_lut=str(identity_lut(tmp_path / "i.cube")),
                      background_lut=str(identity_lut(tmp_path / "i2.cube")),
                      skin_lut=str(identity_lut(tmp_path / "k.cube")))
    gone = {str(BARS): TakeMatte(subject=str(tmp_path / "gone.mp4"), skin=str(tmp_path / "gone.mp4"))}
    look = Look(lut=str(dark_lut(tmp_path / "d.cube")), zone_grade=grade, mattes=gone)
    plain = halves(EditProgram(**BASE), tmp_path, "plain")
    fallback = halves(EditProgram(**BASE, look=look), tmp_path, "fallback")
    assert fallback[0] < plain[0] - 10 and fallback[1] < plain[1] - 10


from halfheaven.previews import background


def test_a_preview_is_graded_the_way_the_render_is(tmp_path):
    grade = ZoneGrade(subject_lut=str(identity_lut(tmp_path / "i.cube")),
                      background_lut=str(dark_lut(tmp_path / "d.cube")),
                      skin_lut=str(identity_lut(tmp_path / "k.cube")))
    left = write_matte_video(BARS, LeftHalf(), tmp_path / "left.mp4", feather=0)
    nothing = write_matte_video(BARS, Nothing(), tmp_path / "none.mp4", feather=0)
    plain = gray(background(BARS, 1.0, Look(), tmp_path / "plain.png"))
    graded = gray(background(BARS, 1.0, Look(zone_grade=grade), tmp_path / "graded.png",
                             subject=left, skin=nothing, height=568))
    assert graded[:, 20:140].mean() == pytest.approx(plain[:, 20:140].mean(), abs=4)
    assert graded[:, 180:300].mean() < plain[:, 180:300].mean() - 10
