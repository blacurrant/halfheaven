"""Subject mattes and behind-the-subject captions.

The segmenter is an interface, not a hard dependency: these tests drive it with
a stub that marks a known rectangle, so the compositing is verified without a
2GB model. Whether the matte comes from SAM2, RVM or anything else is the
segmenter's business and nothing else's.
"""
import pathlib

import numpy as np
import pytest
from PIL import Image

from halfheaven.analyze.segment import write_matte_video
from halfheaven.media.probe import probe
from halfheaven.render.video import build_finish_command, extract_frame, render
from halfheaven.schemas import Canvas, Caption, CaptionProfile, EditProgram, Look, VideoClip

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SOURCE = FIXTURES / "three_shots_at_1.0_3.0.mp4"       # 4.5s, 320x568
CANVAS = Canvas(width=320, height=568, fps=30)


class LowerHalfSubject:
    """Stands in for a person occupying the bottom half of frame."""

    def mask_for(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[height // 2 :, :] = 255
        return mask


def graph_of(command):
    return command[command.index("-filter_complex") + 1] if "-filter_complex" in command else ""


# --- producing the matte ------------------------------------------------------


def test_matte_video_is_written(tmp_path):
    out = write_matte_video(SOURCE, LowerHalfSubject(), tmp_path / "m.mp4")
    assert out.exists() and probe(out).duration == pytest.approx(4.5, abs=0.2)


def test_matte_keeps_the_source_frame_size(tmp_path):
    out = write_matte_video(SOURCE, LowerHalfSubject(), tmp_path / "m.mp4")
    info = probe(out)
    assert (info.width, info.height) == (320, 568)


def test_matte_is_white_on_the_subject_and_black_elsewhere(tmp_path):
    out = write_matte_video(SOURCE, LowerHalfSubject(), tmp_path / "m.mp4")
    frame = np.array(Image.open(extract_frame(out, 1.0, tmp_path / "f.png")).convert("L"))
    assert frame[:200].mean() < 40      # background
    assert frame[-200:].mean() > 215    # subject


# --- compositing --------------------------------------------------------------


def program(**overrides):
    base = dict(
        canvas=CANVAS,
        video=[VideoClip(src=str(SOURCE), start=0.0, end=3.0)],
        captions=[Caption(t=0.0, duration=2.5, text="BEHIND", style="s", behind=True)],
        styles={"s": CaptionProfile(present=True, anchor=(0.5, 0.75), size_pct=0.1, fill_hex="#FF0000")},
    )
    base.update(overrides)
    return EditProgram(**base)


def test_the_finish_pass_takes_the_matte_as_an_input(tmp_path):
    command = build_finish_command(
        program(look=Look(matte="m.mp4")), tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path
    )
    assert "m.mp4" in command


def test_the_subject_is_cut_out_with_alphamerge(tmp_path):
    command = build_finish_command(
        program(look=Look(matte="m.mp4")), tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path
    )
    assert "alphamerge" in graph_of(command)


def test_the_caption_is_composited_before_the_subject(tmp_path):
    # the whole point: the subject must be layered ON TOP of the caption
    graph = graph_of(build_finish_command(
        program(look=Look(matte="m.mp4")), tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path
    ))
    assert graph.index("alphamerge") < graph.rindex("overlay="), "subject must composite last"


def test_no_matte_means_no_alphamerge(tmp_path):
    command = build_finish_command(program(), tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path)
    assert "alphamerge" not in graph_of(command)


def test_a_matte_leaves_captions_not_marked_behind_in_front(tmp_path):
    # A matte makes the effect possible; a caption has to ask for it.
    front = [Caption(t=0.0, duration=2.5, text="FRONT", style="s")]
    command = build_finish_command(program(captions=front, look=Look(matte="m.mp4")),
                                   tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path)
    assert "alphamerge" not in graph_of(command) and "m.mp4" not in command


def test_front_captions_are_composited_over_the_subject(tmp_path):
    both = [Caption(t=0.0, duration=1.0, text="BEHIND", style="s", behind=True),
            Caption(t=1.5, duration=1.0, text="FRONT", style="s")]
    graph = graph_of(build_finish_command(program(captions=both, look=Look(matte="m.mp4")),
                                          tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path))
    assert graph.index("alphamerge") < graph.rindex("overlay=")
    assert graph.rindex("[vs]") < graph.rindex("overlay="), "front layer must go on last"


# --- the effect itself --------------------------------------------------------


def test_a_caption_is_hidden_where_the_subject_covers_it(tmp_path):
    # Measured as a difference against a caption-free render rather than by
    # colour: the fixture is colour bars and already contains every hue, so
    # counting "red pixels" counts the source's own red too.
    matte = write_matte_video(SOURCE, LowerHalfSubject(), tmp_path / "m.mp4")

    clean = render(program(captions=[]), tmp_path / "clean.mp4", work_dir=tmp_path / "w0")
    plain = render(program(), tmp_path / "plain.mp4", work_dir=tmp_path / "w1")
    behind = render(program(look=Look(matte=str(matte))), tmp_path / "behind.mp4",
                    work_dir=tmp_path / "w2")

    def band(video, name):
        frame = np.array(
            Image.open(extract_frame(video, 1.0, tmp_path / name)).convert("RGB")
        ).astype(int)
        top = int(CANVAS.height * 0.66)   # the caption band, inside the subject
        return frame[top:]

    reference = band(clean, "c.png")
    visible_without_matte = (np.abs(band(plain, "p.png") - reference).sum(axis=2) > 60).sum()
    visible_behind_subject = (np.abs(band(behind, "b.png") - reference).sum(axis=2) > 60).sum()

    assert visible_without_matte > 500, "caption should be visible with no matte"
    assert visible_behind_subject < visible_without_matte * 0.2


# --- video-native segmenters --------------------------------------------------
# The per-frame interface suits MediaPipe and misfits SAM2, whose whole
# advantage is propagating one prompt through a clip with temporal memory.
# Both shapes are accepted; a video-native one is asked for the whole clip.


class WholeClipSubject:
    """A video-native stand-in: sees the clip, returns a mask per frame."""

    def __init__(self):
        self.calls = 0

    def masks_for_video(self, video, size):
        self.calls += 1
        width, height = size
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[height // 2 :, :] = 255
        while True:
            yield mask


def test_a_video_native_segmenter_is_accepted(tmp_path):
    out = write_matte_video(SOURCE, WholeClipSubject(), tmp_path / "m.mp4")
    assert out.exists() and probe(out).duration == pytest.approx(4.5, abs=0.2)


def test_a_video_native_segmenter_sees_the_clip_once(tmp_path):
    segmenter = WholeClipSubject()
    write_matte_video(SOURCE, segmenter, tmp_path / "m.mp4")
    assert segmenter.calls == 1, "a video model must not be re-prompted per frame"


def test_both_interfaces_produce_the_same_matte(tmp_path):
    per_frame = write_matte_video(SOURCE, LowerHalfSubject(), tmp_path / "a.mp4")
    whole_clip = write_matte_video(SOURCE, WholeClipSubject(), tmp_path / "b.mp4")
    a = np.array(Image.open(extract_frame(per_frame, 1.0, tmp_path / "a.png")).convert("L"))
    b = np.array(Image.open(extract_frame(whole_clip, 1.0, tmp_path / "b.png")).convert("L"))
    assert np.abs(a.astype(int) - b.astype(int)).mean() < 8
