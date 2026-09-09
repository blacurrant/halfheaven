"""Applying the reference's look: grade, letterbox and animated punch-in.

These are the parts that make an output read as the same edit. Captions alone
change what a video says, not what it looks like.
"""
import pathlib

import numpy as np
import pytest
from PIL import Image

from halfheaven.render.lut import ColorStats, write_lut
from halfheaven.render.video import extract_frame, render
from halfheaven.schemas import Canvas, EditProgram, Look, VideoClip

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SOURCE = FIXTURES / "three_shots_at_1.0_3.0.mp4"
CANVAS = Canvas(width=320, height=568, fps=30)


def program(**overrides):
    base = dict(canvas=CANVAS, video=[VideoClip(src=str(SOURCE), start=0.0, end=2.0)])
    base.update(overrides)
    return EditProgram(**base)


def frame_at(out, t, tmp_path, name="f.png"):
    path = tmp_path / name
    extract_frame(out, t, path)
    return np.array(Image.open(path).convert("RGB")).astype(int)


def test_letterbox_bars_are_black(tmp_path):
    out = render(program(look=Look(letterbox_top_pct=0.15, letterbox_bottom_pct=0.15)),
                 tmp_path / "o.mp4", work_dir=tmp_path)
    pixels = frame_at(out, 1.0, tmp_path)
    assert pixels[:60].mean() < 12      # top bar
    assert pixels[-60:].mean() < 12     # bottom bar


def test_content_survives_between_the_bars(tmp_path):
    out = render(program(look=Look(letterbox_top_pct=0.15, letterbox_bottom_pct=0.15)),
                 tmp_path / "o.mp4", work_dir=tmp_path)
    pixels = frame_at(out, 1.0, tmp_path)
    assert pixels[150:400].mean() > 25


def test_no_bars_when_the_look_has_none(tmp_path):
    out = render(program(), tmp_path / "o.mp4", work_dir=tmp_path)
    pixels = frame_at(out, 1.0, tmp_path)
    assert pixels[:60].mean() > 12


def test_a_darkening_lut_darkens_the_output(tmp_path):
    lut = write_lut(
        ColorStats(mean=(60.0, 0.0, 0.0), std=(20.0, 10.0, 10.0)),
        ColorStats(mean=(25.0, 0.0, 0.0), std=(12.0, 10.0, 10.0)),
        tmp_path / "g.cube", size=17,
    )
    plain = render(program(), tmp_path / "plain.mp4", work_dir=tmp_path)
    graded = render(program(look=Look(lut=str(lut))), tmp_path / "graded.mp4", work_dir=tmp_path)
    assert frame_at(graded, 1.0, tmp_path, "g.png").mean() < frame_at(plain, 1.0, tmp_path, "p.png").mean()


def test_punch_in_is_animated_rather_than_static(tmp_path):
    punched = EditProgram(
        canvas=CANVAS,
        video=[VideoClip(src=str(SOURCE), start=0.0, end=2.0, scale_to=1.35)],
    )
    out = render(punched, tmp_path / "o.mp4", work_dir=tmp_path)
    early = frame_at(out, 0.03, tmp_path, "early.png")
    late = frame_at(out, 1.2, tmp_path, "late.png")
    # a static zoom would leave these near-identical; an animated one does not
    assert np.abs(early - late).mean() > 4.0


# --- punch-in duration --------------------------------------------------------
# zoompan's d=1 did not take effect: a punched clip emitted ~512 output frames
# per input frame, turning an 11.3s segment into 5792s. Nothing caught it - the
# duration test used unpunched clips, and the animation test only checked that
# two frames differ, which is also true of a broken 96-minute segment.


def test_a_punched_segment_keeps_its_clip_duration(tmp_path):
    import subprocess

    from halfheaven.media.probe import probe
    from halfheaven.render.video import build_segment_command

    clip = VideoClip(src=str(SOURCE), start=0.0, end=0.5, scale_to=1.35)
    out = tmp_path / "seg.mp4"
    subprocess.run(
        build_segment_command(clip, CANVAS, out, with_audio=False),
        check=True, capture_output=True,
    )
    assert probe(out).duration == pytest.approx(0.5, abs=0.1)


def test_an_unpunched_segment_keeps_its_clip_duration(tmp_path):
    import subprocess

    from halfheaven.media.probe import probe
    from halfheaven.render.video import build_segment_command

    clip = VideoClip(src=str(SOURCE), start=1.0, end=1.5)
    out = tmp_path / "seg.mp4"
    subprocess.run(
        build_segment_command(clip, CANVAS, out, with_audio=False),
        check=True, capture_output=True,
    )
    assert probe(out).duration == pytest.approx(0.5, abs=0.1)
