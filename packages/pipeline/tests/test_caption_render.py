"""Rendering a caption card to an RGBA overlay.

ffmpeg here has no drawtext or libass, and even where it does, drawtext cannot
do per-word highlighting or animation. Caption cards are drawn with Pillow and
composited, which also makes them assertable: the tests read the pixels.
"""
import numpy as np
import pytest
from PIL import Image

from halfheaven.render.captions import render_caption
from halfheaven.schemas import Canvas, CaptionProfile, TextRun

CANVAS = Canvas(width=540, height=960, fps=30)
PROFILE = CaptionProfile(present=True, anchor=(0.5, 0.75), size_pct=0.05, fill_hex="#FFE94A")


def card(text, path, profile=PROFILE):
    """A single-style caption card, the common case."""
    return render_caption([TextRun(text=text)], CANVAS, {"default": profile}, path)


def alpha_of(path):
    return np.array(Image.open(path))[:, :, 3]


def test_card_matches_the_canvas_size(tmp_path):
    path = card("HELLO", tmp_path / "c.png", PROFILE)
    assert Image.open(path).size == (540, 960)


def test_card_is_transparent_apart_from_the_text(tmp_path):
    alpha = alpha_of(card("HELLO", tmp_path / "c.png", PROFILE))
    assert (alpha == 0).mean() > 0.85


def test_text_is_drawn_at_the_profile_anchor(tmp_path):
    alpha = alpha_of(card("HELLO", tmp_path / "c.png", PROFILE))
    rows, cols = np.nonzero(alpha)
    assert rows.mean() / 960 == pytest.approx(0.75, abs=0.05)
    assert cols.mean() / 540 == pytest.approx(0.50, abs=0.05)


def test_text_is_drawn_in_the_profile_fill_colour(tmp_path):
    path = card("HELLO", tmp_path / "c.png", PROFILE)
    pixels = np.array(Image.open(path))
    opaque = pixels[pixels[:, :, 3] > 250]
    # the glyph body is the brightest opaque cluster; the stroke is black
    brightest = opaque[opaque[:, :3].sum(axis=1).argmax()]
    assert tuple(brightest[:3]) == (255, 233, 74)


def test_long_text_wraps_instead_of_overflowing_the_frame(tmp_path):
    long_text = "THIS IS A VERY LONG CAPTION THAT CANNOT POSSIBLY FIT ON ONE LINE"
    alpha = alpha_of(card(long_text, tmp_path / "c.png", PROFILE))
    _, cols = np.nonzero(alpha)
    assert cols.min() >= 0 and cols.max() <= 539
    rows, _ = np.nonzero(alpha)
    # more than one line means the drawn block is taller than a single cap height
    assert (rows.max() - rows.min()) > 0.05 * 960


def test_empty_text_produces_a_fully_transparent_card(tmp_path):
    alpha = alpha_of(card("", tmp_path / "c.png", PROFILE))
    assert alpha.max() == 0


# --- legibility is a floor, not a style choice --------------------------------
# Observed on real output: the reference's captions sit on a dark letterbox bar
# and need no outline, so the profile carried stroke_heavy=False. Composited
# over bright, busy footage the same captions were barely readable. A caption
# over arbitrary video always gets edge separation.

NO_STROKE = CaptionProfile(present=True, anchor=(0.5, 0.5), size_pct=0.08,
                           fill_hex="#FFE94A", stroke_heavy=False)


def test_a_caption_always_gets_an_outline_even_when_the_reference_had_none(tmp_path):
    path = card("HELLO", tmp_path / "c.png", NO_STROKE)
    pixels = np.array(Image.open(path))
    opaque = pixels[pixels[:, :, 3] > 250]
    darkest = opaque[opaque[:, :3].sum(axis=1).argmin()]
    assert darkest[:3].sum() < 60  # black outline pixels are present


def test_a_heavy_stroke_is_thicker_than_the_minimum(tmp_path):
    heavy = CaptionProfile(present=True, anchor=(0.5, 0.5), size_pct=0.08,
                           fill_hex="#FFE94A", stroke_heavy=True)
    thin_alpha = alpha_of(card("HELLO", tmp_path / "thin.png", NO_STROKE))
    heavy_alpha = alpha_of(card("HELLO", tmp_path / "heavy.png", heavy))
    assert (heavy_alpha > 0).sum() > (thin_alpha > 0).sum()
