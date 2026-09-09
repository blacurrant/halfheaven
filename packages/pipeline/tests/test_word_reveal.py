"""Word-by-word reveal and per-word emphasis.

Whisper already gives word timings and the caption track is already a concat of
stills with durations, so a reveal is simply more stills - one per word state -
built by the same mechanism. Each state shows one more word than the last.
"""
import pathlib

import numpy as np
import pytest
from PIL import Image

from halfheaven.render.captions import build_caption_track, render_caption
from halfheaven.schemas import Canvas, Caption, CaptionProfile, EditProgram, TextRun, VideoClip

CANVAS = Canvas(width=320, height=568, fps=30)
BODY = CaptionProfile(present=True, size_pct=0.05, font_category="mono", fill_hex="#FFE94A")
LOUD = CaptionProfile(present=True, size_pct=0.13, font_category="didone", fill_hex="#FFE94A")
STYLES = {"default": BODY, "loud": LOUD}


def program(captions):
    return EditProgram(
        canvas=CANVAS,
        video=[VideoClip(src="a.mp4", start=0.0, end=10.0)],
        captions=captions,
        styles=STYLES,
    )


def entries(list_path: pathlib.Path):
    out, current = [], None
    for line in list_path.read_text().splitlines():
        if line.startswith("file "):
            current = line.split("'")[1]
        elif line.startswith("duration ") and current:
            out.append((pathlib.Path(current).name, float(line.split()[1])))
    return out


def ink(path):
    return (np.array(Image.open(path))[:, :, 3] > 0).sum()


# --- the model ---------------------------------------------------------------


def test_a_plain_caption_still_works_without_runs():
    caption = Caption(t=0.0, duration=1.0, text="hello there")
    assert caption.plain_text == "hello there"


def test_runs_carry_their_own_style():
    caption = Caption(
        t=0.0, duration=1.0,
        runs=[TextRun(text="money", style="default"), TextRun(text="SALT", style="loud")],
    )
    assert [r.style for r in caption.runs] == ["default", "loud"]


def test_plain_text_joins_the_runs():
    caption = Caption(t=0.0, duration=1.0,
                      runs=[TextRun(text="a"), TextRun(text="b"), TextRun(text="c")])
    assert caption.plain_text == "a b c"


def test_a_caption_needs_either_text_or_runs():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Caption(t=0.0, duration=1.0)


# --- reveal ------------------------------------------------------------------


def test_a_card_with_word_times_becomes_one_still_per_word(tmp_path):
    caption = Caption(t=0.0, duration=1.5, runs=[
        TextRun(text="one", t=0.0), TextRun(text="two", t=0.5), TextRun(text="three", t=1.0),
    ])
    cards = [n for n, _ in entries(build_caption_track(program([caption]), tmp_path))
             if n.startswith("caption_")]
    assert len(cards) == 3


def test_each_reveal_state_lasts_until_the_next_word(tmp_path):
    caption = Caption(t=0.0, duration=1.5, runs=[
        TextRun(text="one", t=0.0), TextRun(text="two", t=0.5), TextRun(text="three", t=1.0),
    ])
    durations = [d for n, d in entries(build_caption_track(program([caption]), tmp_path))
                 if n.startswith("caption_")]
    assert durations == pytest.approx([0.5, 0.5, 0.5], abs=0.01)


def test_each_state_shows_more_text_than_the_one_before(tmp_path):
    caption = Caption(t=0.0, duration=1.5, runs=[
        TextRun(text="one", t=0.0), TextRun(text="two", t=0.5), TextRun(text="three", t=1.0),
    ])
    build_caption_track(program([caption]), tmp_path)
    cards = sorted(tmp_path.glob("caption_*.png"))
    inks = [ink(c) for c in cards]
    assert inks == sorted(inks) and inks[0] < inks[-1]


def test_a_card_without_word_times_stays_a_single_still(tmp_path):
    caption = Caption(t=0.0, duration=1.0, text="all at once")
    cards = [n for n, _ in entries(build_caption_track(program([caption]), tmp_path))
             if n.startswith("caption_")]
    assert len(cards) == 1


# --- mixed styles ------------------------------------------------------------


def test_an_emphasised_run_renders_larger_than_a_body_run(tmp_path):
    quiet = render_caption([TextRun(text="SALT")], CANVAS, STYLES, tmp_path / "q.png")
    loud = render_caption([TextRun(text="SALT", style="loud")], CANVAS, STYLES, tmp_path / "l.png")
    assert ink(loud) > ink(quiet) * 2


# --- fitting -----------------------------------------------------------------
# Observed in real output: emphasis words rendered at 2.6x the body size were
# wider than the frame and clipped at both edges ("IPHONE," lost both ends).
# A single word cannot wrap, so it has to shrink.

HUGE = CaptionProfile(present=True, size_pct=0.16, font_category="didone", fill_hex="#FFE94A")


def bounds(path):
    alpha = np.array(Image.open(path))[:, :, 3]
    rows, cols = np.nonzero(alpha)
    return cols.min(), cols.max(), rows.min(), rows.max()


def test_a_long_emphasis_word_is_shrunk_to_fit_the_frame(tmp_path):
    # Pillow clips overflowing text at the image edge, so a clipped word still
    # reports coordinates inside the frame. The detectable signature of
    # clipping is ink *touching* the boundary, not exceeding it.
    path = render_caption([TextRun(text="CAPITALISM", style="huge")], CANVAS,
                          {"huge": HUGE}, tmp_path / "c.png")
    left, right, _, _ = bounds(path)
    assert left > 0, "text is clipped at the left edge"
    assert right < CANVAS.width - 1, "text is clipped at the right edge"


def test_a_shrunk_word_still_fills_most_of_the_width(tmp_path):
    # shrink to fit, not shrink to nothing
    path = render_caption([TextRun(text="CAPITALISM", style="huge")], CANVAS,
                          {"huge": HUGE}, tmp_path / "c.png")
    left, right, _, _ = bounds(path)
    assert (right - left) > CANVAS.width * 0.6


def test_a_short_word_is_not_shrunk(tmp_path):
    small = render_caption([TextRun(text="OIL", style="huge")], CANVAS, {"huge": HUGE}, tmp_path / "a.png")
    _, _, top, bottom = bounds(small)
    assert (bottom - top) > CANVAS.height * 0.10  # kept its full size


def test_the_caption_block_stays_inside_the_frame_vertically(tmp_path):
    caption = [TextRun(text="money"), TextRun(text="ATTRACTS", style="huge")]
    path = render_caption(caption, CANVAS, {"default": BODY, "huge": HUGE}, tmp_path / "c.png")
    _, _, top, bottom = bounds(path)
    assert top > 0, "caption block is clipped at the top"
    assert bottom < CANVAS.height - 1, "caption block is clipped at the bottom"
