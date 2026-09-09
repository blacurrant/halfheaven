"""Building captions as one track instead of one overlay each.

Rendering 46 captions as 46 looped image inputs got the ffmpeg process killed
(exit -9): each input holds a full-size RGBA still open for the whole program.
Captions never overlap, so they belong on a single track composited with a
single overlay - constant cost regardless of how many captions there are.
"""
import pathlib

import pytest

from halfheaven.render.captions import build_caption_track
from halfheaven.schemas import Canvas, Caption, CaptionProfile, EditProgram, VideoClip

CANVAS = Canvas(width=320, height=568, fps=30)
STYLES = {"default": CaptionProfile(present=True, size_pct=0.06)}


def program(captions):
    return EditProgram(
        canvas=CANVAS,
        video=[VideoClip(src="a.mp4", start=0.0, end=10.0)],
        captions=captions,
        styles=STYLES,
    )


def entries(list_path: pathlib.Path):
    """(file, duration) pairs from an ffmpeg concat list."""
    out, current = [], None
    for line in list_path.read_text().splitlines():
        if line.startswith("file "):
            current = line.split("'")[1]
        elif line.startswith("duration ") and current:
            out.append((pathlib.Path(current).name, float(line.split()[1])))
    return out


def test_track_covers_the_whole_program(tmp_path):
    prog = program([Caption(t=2.0, duration=1.0, text="hi")])
    listing = entries(build_caption_track(prog, tmp_path))
    assert sum(duration for _, duration in listing) == pytest.approx(10.0, abs=0.01)


def test_a_gap_before_the_first_caption_is_transparent(tmp_path):
    prog = program([Caption(t=2.0, duration=1.0, text="hi")])
    first_file, first_duration = entries(build_caption_track(prog, tmp_path))[0]
    assert "blank" in first_file and first_duration == pytest.approx(2.0)


def test_the_caption_occupies_its_own_window(tmp_path):
    prog = program([Caption(t=2.0, duration=1.0, text="hi")])
    listing = entries(build_caption_track(prog, tmp_path))
    assert listing[1][0].startswith("caption_") and listing[1][1] == pytest.approx(1.0)


def test_a_program_with_no_captions_is_one_transparent_span(tmp_path):
    listing = entries(build_caption_track(program([]), tmp_path))
    assert len(listing) == 1 and "blank" in listing[0][0]


def test_back_to_back_captions_need_no_gap_between_them(tmp_path):
    prog = program([Caption(t=0.0, duration=1.0, text="a"), Caption(t=1.0, duration=1.0, text="b")])
    listing = entries(build_caption_track(prog, tmp_path))
    assert [name.startswith("caption_") for name, _ in listing[:2]] == [True, True]


def test_captions_are_ordered_by_time(tmp_path):
    prog = program([Caption(t=5.0, duration=1.0, text="late"), Caption(t=1.0, duration=1.0, text="early")])
    listing = entries(build_caption_track(prog, tmp_path))
    cards = [name for name, _ in listing if name.startswith("caption_")]
    assert len(cards) == 2
    assert listing.index((cards[0], 1.0)) < listing.index((cards[1], 1.0))


def test_every_listed_file_can_actually_be_opened(tmp_path, monkeypatch):
    # The concat demuxer resolves 'file' entries relative to the LIST's own
    # directory, so a RELATIVE work dir wrote work/... into a list living in
    # work/, which ffmpeg resolved as work/work/... and could not open.
    # The CLI passes --work work, so the relative case is the real one.
    monkeypatch.chdir(tmp_path)
    prog = program([Caption(t=2.0, duration=1.0, text="hi")])
    listing = build_caption_track(prog, pathlib.Path("work"))
    referenced = [line.split("'")[1] for line in listing.read_text().splitlines() if line.startswith("file ")]
    assert referenced, "the track lists no files"
    for path in referenced:
        assert pathlib.Path(path).is_absolute(), f"{path} is relative to the list, not to ffmpeg's cwd"
        assert pathlib.Path(path).exists(), f"{path} does not exist"
