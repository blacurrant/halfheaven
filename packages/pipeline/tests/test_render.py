"""Rendering an EditProgram to a real MP4.

The renderer is a pure function of the program: it never sees a StyleProfile,
a transcript, or a model response. Everything it needs, including caption
visual style, travels inside the program.
"""
import pathlib

import numpy as np
import pytest
from PIL import Image

from halfheaven.media.probe import probe
from halfheaven.render.video import render
from halfheaven.schemas import Canvas, Caption, CaptionProfile, EditProgram, VideoClip

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SOURCE = FIXTURES / "three_shots_at_1.0_3.0.mp4"      # 4.5s, 320x568, no audio
WITH_AUDIO = FIXTURES / "with_audio_track.mp4"        # 3.0s, 320x568, has audio
CANVAS = Canvas(width=320, height=568, fps=30)


def two_clip_program(**overrides):
    base = dict(
        canvas=CANVAS,
        video=[
            VideoClip(src=str(SOURCE), start=0.0, end=1.0),
            VideoClip(src=str(SOURCE), start=3.0, end=4.0),
        ],
    )
    base.update(overrides)
    return EditProgram(**base)


def test_render_produces_a_file(tmp_path):
    out = render(two_clip_program(), tmp_path / "out.mp4", work_dir=tmp_path)
    assert out.exists() and out.stat().st_size > 0


def test_rendered_duration_matches_the_program(tmp_path):
    out = render(two_clip_program(), tmp_path / "out.mp4", work_dir=tmp_path)
    assert probe(out).duration == pytest.approx(2.0, abs=0.15)


def test_rendered_frame_size_matches_the_canvas(tmp_path):
    out = render(two_clip_program(), tmp_path / "out.mp4", work_dir=tmp_path)
    info = probe(out)
    assert (info.width, info.height) == (320, 568)


def test_source_without_audio_still_renders(tmp_path):
    # both supplied sample videos had no audio track; this must not crash
    out = render(two_clip_program(), tmp_path / "out.mp4", work_dir=tmp_path)
    assert probe(out).has_audio is False


def test_source_with_audio_keeps_its_audio(tmp_path):
    program = EditProgram(
        canvas=CANVAS,
        video=[VideoClip(src=str(WITH_AUDIO), start=0.0, end=1.5)],
    )
    out = render(program, tmp_path / "out.mp4", work_dir=tmp_path)
    assert probe(out).has_audio is True


def test_caption_is_burned_into_the_frame(tmp_path):
    program = two_clip_program(
        captions=[Caption(t=0.2, duration=1.0, text="HELLO", style="s1")],
        styles={"s1": CaptionProfile(present=True, anchor=(0.5, 0.5), size_pct=0.09, fill_hex="#FFE94A")},
    )
    out = render(program, tmp_path / "out.mp4", work_dir=tmp_path)
    frame = tmp_path / "f.png"
    from halfheaven.render.video import extract_frame

    extract_frame(out, 0.6, frame)
    pixels = np.array(Image.open(frame).convert("RGB")).reshape(-1, 3).astype(int)
    # the caption fill should be present somewhere in the frame
    distance = np.abs(pixels - np.array([255, 233, 74])).sum(axis=1)
    assert distance.min() < 40


def test_frame_outside_the_caption_window_has_no_caption(tmp_path):
    program = two_clip_program(
        captions=[Caption(t=0.0, duration=0.3, text="HELLO", style="s1")],
        styles={"s1": CaptionProfile(present=True, anchor=(0.5, 0.5), size_pct=0.09, fill_hex="#FFE94A")},
    )
    out = render(program, tmp_path / "out.mp4", work_dir=tmp_path)
    frame = tmp_path / "f.png"
    from halfheaven.render.video import extract_frame

    extract_frame(out, 1.5, frame)
    pixels = np.array(Image.open(frame).convert("RGB")).reshape(-1, 3).astype(int)
    distance = np.abs(pixels - np.array([255, 233, 74])).sum(axis=1)
    assert distance.min() > 40
