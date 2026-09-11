"""The shape of the render.

Three separate renders were killed at 3.5-4.8GB before this file existed. The
cause was structural: `concat=n=16` consumes segments in order, but ffmpeg
opens all 16 inputs at once, so fifteen decoders ran ahead buffering frames
they could not deliver. Removing audio and removing captions each changed
nothing, which is what ruled everything else out.

So a render is now one small process per clip, joined by the concat DEMUXER,
which opens files one at a time. Memory is bounded by a single clip. These
tests assert that structure, because it is invisible from a rendered frame.
"""
import pathlib

from halfheaven.render.video import build_finish_command, build_segment_command
from halfheaven.schemas import Canvas, Caption, CaptionProfile, EditProgram, Look, VideoClip

CANVAS = Canvas(width=320, height=568, fps=30)
SOURCE = str(pathlib.Path(__file__).parent / "fixtures" / "three_shots_at_1.0_3.0.mp4")


def program(clips=3, captions=0, look=None):
    video = [VideoClip(src=SOURCE, start=i * 1.2, end=i * 1.2 + 1.0) for i in range(clips)]
    step = (len(video) / captions) if captions else 0.0
    return EditProgram(
        canvas=CANVAS,
        video=video,
        captions=[Caption(t=i * step, duration=step * 0.8, text=f"c{i}") for i in range(captions)],
        styles={"default": CaptionProfile(present=True)},
        look=look or Look(),
    )


def graph_of(command):
    if "-filter_complex" in command:
        return command[command.index("-filter_complex") + 1]
    return command[command.index("-vf") + 1] if "-vf" in command else ""


def test_a_segment_reads_exactly_one_input(tmp_path):
    command = build_segment_command(program().video[0], CANVAS, tmp_path / "s.mp4", with_audio=False)
    assert command.count("-i") == 1


def test_a_segment_never_uses_the_concat_filter(tmp_path):
    command = build_segment_command(program().video[0], CANVAS, tmp_path / "s.mp4", with_audio=False)
    assert "concat=" not in graph_of(command)


def test_a_segment_seeks_at_the_input(tmp_path):
    clip = program().video[1]
    command = build_segment_command(clip, CANVAS, tmp_path / "s.mp4", with_audio=False)
    assert "-ss" in command and command[command.index("-ss") + 1].startswith("1.2")


def test_a_punched_segment_animates_the_zoom(tmp_path):
    clip = VideoClip(src=SOURCE, start=0.0, end=1.0, scale_to=1.3)
    graph = graph_of(build_segment_command(clip, CANVAS, tmp_path / "s.mp4", with_audio=False))
    # zoompan re-evaluates its window every frame; d=1 keeps one output frame per input
    assert "zoompan=" in graph and ":d=1" in graph, "the zoom must be re-evaluated per frame"


def test_an_unpunched_segment_has_no_zoom(tmp_path):
    command = build_segment_command(program().video[0], CANVAS, tmp_path / "s.mp4", with_audio=False)
    assert "zoompan" not in graph_of(command)


def test_the_finish_pass_reads_at_most_two_inputs(tmp_path):
    command = build_finish_command(
        program(captions=30), tmp_path / "base.mp4", tmp_path / "o.mp4", tmp_path
    )
    assert command.count("-i") <= 2


def test_finish_input_count_does_not_grow_with_captions(tmp_path):
    few = build_finish_command(program(captions=1), tmp_path / "b.mp4", tmp_path / "a.mp4", tmp_path)
    many = build_finish_command(program(captions=40), tmp_path / "b.mp4", tmp_path / "c.mp4", tmp_path)
    assert few.count("-i") == many.count("-i")


def test_the_grade_is_applied_in_the_finish_pass(tmp_path):
    lut = tmp_path / "g.cube"
    lut.write_text("LUT_3D_SIZE 2\n")
    command = build_finish_command(
        program(look=Look(lut=str(lut))), tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path
    )
    assert "lut3d" in graph_of(command)


def test_letterbox_is_applied_in_the_finish_pass(tmp_path):
    command = build_finish_command(
        program(look=Look(letterbox_top_pct=0.1, letterbox_bottom_pct=0.1)),
        tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path,
    )
    assert "pad=" in graph_of(command)
