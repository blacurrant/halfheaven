"""Per-take mattes: produced once, cut like the footage, used by the grade.

The models themselves are stand-ins here. What is tested is everything the
pipeline does around them: gating, the frame grid, carrying a matte through
crops and punch-ins, and holding the grade back on skin.
"""
import pathlib
import subprocess

import numpy as np
import pytest
from PIL import Image

from halfheaven.analyze.matte import (
    BACKGROUND, CLOTHES, FACE_SKIN, matte_take, person_gate,
)
from halfheaven.analyze.segment import write_matte_video
from halfheaven.media.ffmpeg_bin import ffmpeg
from halfheaven.media.probe import probe
from halfheaven.render.lut import ColorStats, write_lut
from halfheaven.render.video import (
    build_mask_segment_command, build_segment_command, extract_frame, mask_track, render,
)
from halfheaven.schemas import Canvas, EditProgram, Look, TakeMatte, VideoClip

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
WIDE = FIXTURES / "wide_subject_moves.mp4"          # 640x360, bright ellipse moving L -> C -> R
BARS = FIXTURES / "three_shots_at_1.0_3.0.mp4"      # 320x568, 4.5s
VERTICAL = Canvas(width=320, height=568, fps=25)


def gray_at(video, t, tmp_path, name):
    return np.array(Image.open(extract_frame(video, t, tmp_path / name)).convert("L")).astype(int)


class Bright:
    """The wide fixture's subject is the only bright thing in it."""

    def mask_for(self, frame):
        return np.where(frame.max(axis=2) > 150, 255, 0).astype(np.uint8)


class LeftHalf:
    def mask_for(self, frame):
        mask = np.zeros(frame.shape[:2], np.uint8)
        mask[:, : frame.shape[1] // 2] = 255
        return mask


# --- carrying a matte through the edit ----------------------------------------


def wide_program(matte):
    return EditProgram(
        canvas=VERTICAL,
        video=[
            VideoClip(src=str(WIDE), start=0.0, end=1.5, crop_x=0.22, scale_to=1.3),
            VideoClip(src=str(WIDE), start=1.7, end=2.8, crop_x=0.5),
            VideoClip(src=str(WIDE), start=3.0, end=4.3, crop_x=0.8, crop_y=0.6),
        ],
        look=Look(mattes={str(WIDE): TakeMatte(subject=str(matte))}),
    )


def overlap(picture, matte):
    subject, marked = picture > 150, matte > 128
    return (subject & marked).sum() / max(1, (subject | marked).sum())


def test_a_mask_segment_frames_the_matte_exactly_as_the_footage(tmp_path):
    clip = wide_program("m.mp4").video[0]
    footage = build_segment_command(clip, VERTICAL, tmp_path / "s.mp4", with_audio=False)
    mask = build_mask_segment_command(clip, "m.mp4", VERTICAL, tmp_path / "m.mp4")
    graph = lambda command: command[command.index("-vf") + 1].split(",")
    assert graph(mask)[:-2] == graph(footage)[:-2], "same cover, crop, rate and zoom"
    assert graph(mask)[-1] == "format=gray" and "-an" in mask


@pytest.mark.parametrize("scale", [1.0, 0.5])
def test_the_subject_track_lands_on_the_subject_through_crops_and_punch_ins(tmp_path, scale):
    matte = write_matte_video(WIDE, Bright(), tmp_path / "full.mp4", feather=0)
    if scale != 1.0:
        # mattes are made at reduced size for large takes; the geometry must not care
        small = tmp_path / "small.mp4"
        subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(matte),
                        "-vf", f"scale={int(640 * scale)}:{int(360 * scale)}", str(small)], check=True)
        matte = small
    program = wide_program(matte)
    render(program, tmp_path / "out.mp4", work_dir=tmp_path / "w")
    track = mask_track(program, "subject", tmp_path / "w")
    # segments round to whole frames, so the footage is the measure, not the program
    assert probe(track).duration == pytest.approx(probe(tmp_path / "w" / "base.mp4").duration, abs=0.02)
    for t in (0.2, 1.2, 2.0, 3.4):  # during the punch-in, after it, and on the later crops
        picture = gray_at(tmp_path / "w" / "base.mp4", t, tmp_path, f"p{t}.png")
        mask = gray_at(track, t, tmp_path, f"m{t}.png")
        assert overlap(picture, mask) > 0.85, f"matte drifted off the subject at {t}s"


def test_no_track_when_any_clip_lacks_a_matte(tmp_path):
    program = wide_program(write_matte_video(WIDE, Bright(), tmp_path / "m.mp4"))
    other = program.video + [VideoClip(src=str(BARS), start=0.0, end=1.0)]
    assert mask_track(program.model_copy(update={"video": other}), "subject", tmp_path) is None


def test_the_subject_track_is_reused_until_the_edit_changes(tmp_path):
    program = wide_program(write_matte_video(WIDE, Bright(), tmp_path / "m.mp4"))
    first = mask_track(program, "subject", tmp_path / "w")
    made = first.stat().st_mtime_ns
    assert mask_track(program, "subject", tmp_path / "w").stat().st_mtime_ns == made
    moved = program.video[:1] + [program.video[1].model_copy(update={"crop_x": 0.3})] + program.video[2:]
    mask_track(program.model_copy(update={"video": moved}), "subject", tmp_path / "w")
    assert first.stat().st_mtime_ns != made


# --- the grade holds back on skin -----------------------------------------------


def test_skin_keeps_more_of_its_own_colour_under_a_grade(tmp_path):
    lut = write_lut(ColorStats(mean=(60.0, 0.0, 0.0), std=(20.0, 10.0, 10.0)),
                    ColorStats(mean=(25.0, 0.0, 0.0), std=(12.0, 10.0, 10.0)),
                    tmp_path / "dark.cube", size=17)
    skin = write_matte_video(BARS, LeftHalf(), tmp_path / "skin.mp4", feather=0)
    mattes = {str(BARS): TakeMatte(subject=str(skin), skin=str(skin))}
    base = dict(canvas=Canvas(width=320, height=568, fps=30),
                video=[VideoClip(src=str(BARS), start=0.0, end=2.0)])

    def left_right(look, name):
        out = render(EditProgram(**base, look=look), tmp_path / f"{name}.mp4", work_dir=tmp_path / name)
        frame = gray_at(out, 1.0, tmp_path, f"{name}.png")
        return frame[:, 20:140].mean(), frame[:, 180:300].mean()

    plain = left_right(Look(), "plain")
    graded = left_right(Look(lut=str(lut)), "graded")
    protected = left_right(Look(lut=str(lut), mattes=mattes, skin_protect=1.0), "protected")
    assert graded[0] < plain[0] - 10, "the grade should darken this footage"
    assert protected[0] == pytest.approx(plain[0], abs=4), "fully protected skin is left as shot"
    assert protected[1] == pytest.approx(graded[1], abs=4), "everything else takes the full grade"


# --- combining the models -------------------------------------------------------


class Opaque:
    """RVM stand-in that claims the whole frame, so only the gate decides."""

    def __init__(self):
        self.resets = 0

    def reset(self):
        self.resets += 1

    def alpha(self, rgb):
        return np.ones(rgb.shape[:2], np.float32)


class LeftPersonTopSkin:
    """Parts stand-in: a person on the left, whose top quarter is face."""

    def __init__(self):
        self.calls = 0

    def parts(self, rgb, t_ms):
        self.calls += 1
        height, width = rgb.shape[:2]
        parts = np.full((height, width), BACKGROUND, np.uint8)
        parts[:, : width // 2] = CLOTHES
        parts[: height // 4, : width // 2] = FACE_SKIN
        return parts


def test_matte_take_gates_the_edge_by_the_person_and_marks_skin(tmp_path):
    parter = LeftPersonTopSkin()
    matte = matte_take(BARS, tmp_path, Opaque(), parter, parts_every=3)
    frames = probe(BARS).duration * 30
    assert probe(matte.subject).duration == pytest.approx(probe(BARS).duration, abs=0.1)
    assert parter.calls == pytest.approx(frames / 3, abs=2), "parts are read every third frame"

    subject = gray_at(matte.subject, 1.0, tmp_path, "s.png")
    skin = gray_at(matte.skin, 1.0, tmp_path, "k.png")
    assert subject[:, :140].mean() > 245, "RVM's alpha survives inside the person"
    assert subject[:, 200:].mean() < 5, "and is removed where the parts say background"
    assert skin[:120, :140].mean() > 245 and skin[250:, :140].mean() < 5


def test_the_gate_grows_past_the_person_but_not_far(tmp_path):
    parts = np.full((1280, 720), BACKGROUND, np.uint8)
    parts[400:900, 200:500] = CLOTHES
    gate = person_gate(parts)
    assert gate[400:900, 200:500].min() > 0.99, "never clips the person"
    assert gate[650, 195] > 0.9, "reaches hair a few pixels beyond the mask"
    assert gate[650, 100] < 0.01, "but not the table a hand's width away"


# --- a solid background behind the subject --------------------------------------


def test_the_background_becomes_the_chosen_colour_and_the_subject_stays(tmp_path):
    subject = write_matte_video(BARS, LeftHalf(), tmp_path / "subject.mp4", feather=0)
    base = dict(canvas=Canvas(width=320, height=568, fps=30),
                video=[VideoClip(src=str(BARS), start=0.0, end=2.0)])
    look = Look(mattes={str(BARS): TakeMatte(subject=str(subject))}, background_hex="#1E90FF")

    plain = render(EditProgram(**base), tmp_path / "plain.mp4", work_dir=tmp_path / "p")
    swapped = render(EditProgram(**base, look=look), tmp_path / "bg.mp4", work_dir=tmp_path / "b")
    colour = lambda v, n: np.array(Image.open(extract_frame(v, 1.0, tmp_path / n)).convert("RGB")).astype(int)
    before, after = colour(plain, "a.png"), colour(swapped, "b.png")

    background = after[:, 200:300].reshape(-1, 3).mean(axis=0)
    assert np.abs(background - (0x1E, 0x90, 0xFF)).max() < 12, "background is the chosen colour"
    assert np.abs(after[:, 20:140] - before[:, 20:140]).mean() < 4, "the subject is untouched"


def test_no_matte_means_the_background_is_left_alone(tmp_path):
    program = EditProgram(canvas=Canvas(width=320, height=568, fps=30),
                          video=[VideoClip(src=str(BARS), start=0.0, end=1.0)],
                          look=Look(background_hex="#000000"))
    from halfheaven.render.video import build_finish_command
    command = build_finish_command(program, tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path)
    assert "drawbox" not in " ".join(command)


def test_a_background_colour_must_be_a_hex_colour():
    with pytest.raises(Exception):
        Look(background_hex="red; rm -rf /")
