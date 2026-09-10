"""The caption engine, as composable axes rather than named looks.

Every style creators name - Hormozi, MrBeast, sticker, typewriter - is a
combination of five independent choices: how words are grouped, how they are
revealed, how each enters, how the active word is marked, and how the text sits
on the footage. Building the axes rather than the looks means a new style is a
few field changes, not a new renderer.
"""
import numpy as np
import pytest
from PIL import Image

from halfheaven.render.captions import render_frame
from halfheaven.render.caption_frames import CaptionFrame
from halfheaven.schemas import Canvas, CaptionProfile, TextRun

CANVAS = Canvas(width=360, height=640, fps=30)
WORDS = [TextRun(text="money"), TextRun(text="attracts"), TextRun(text="money")]


def base(**kw) -> CaptionProfile:
    return CaptionProfile(present=True, size_pct=0.06, font_category="grotesque",
                          fill_hex="#FFFFFF", **kw)


def px(path):
    return np.array(Image.open(path))


def ink(path):
    return (px(path)[:, :, 3] > 0).sum()


def has_colour(path, rgb, tol=26):
    a = px(path)
    m = a[:, :, 3] > 200
    if not m.any():
        return False
    return (np.abs(a[:, :, :3][m].astype(int) - np.array(rgb)).sum(axis=1) < tol).any()


def frame(tmp_path, profile, name="c.png", **kw):
    f = CaptionFrame(runs=WORDS, duration=0.3, **kw)
    return render_frame(f, CANVAS, profile, tmp_path / name)


# --- reveal -------------------------------------------------------------------

def test_karaoke_keeps_every_word_on_screen(tmp_path):
    all_words = ink(frame(tmp_path, base(reveal="karaoke"), "a.png", visible=3, active=1))
    one_word = ink(frame(tmp_path, base(reveal="append"), "b.png", visible=1))
    assert all_words > one_word * 2


def test_karaoke_marks_the_active_word_in_its_own_colour(tmp_path):
    p = base(reveal="karaoke", active="colour", active_fill_hex="#FFE94A")
    assert has_colour(frame(tmp_path, p, "c.png", visible=3, active=1), (255, 233, 74))


def test_a_non_active_word_keeps_the_body_colour(tmp_path):
    p = base(reveal="karaoke", active="colour", active_fill_hex="#FFE94A")
    assert has_colour(frame(tmp_path, p, "c.png", visible=3, active=1), (255, 255, 255))


def test_append_shows_one_more_word_each_state(tmp_path):
    a = ink(frame(tmp_path, base(reveal="append"), "1.png", visible=1))
    b = ink(frame(tmp_path, base(reveal="append"), "2.png", visible=2))
    assert b > a


# --- enter --------------------------------------------------------------------

def test_a_popping_word_starts_smaller_than_it_ends(tmp_path):
    p = base(enter="pop")
    start = ink(frame(tmp_path, p, "s.png", visible=1, entering=0, progress=0.0))
    end = ink(frame(tmp_path, p, "e.png", visible=1, entering=0, progress=1.0))
    assert start < end * 0.92


def test_without_pop_the_word_is_full_size_immediately(tmp_path):
    p = base(enter="none")
    start = ink(frame(tmp_path, p, "s.png", visible=1, entering=0, progress=0.0))
    end = ink(frame(tmp_path, p, "e.png", visible=1, entering=0, progress=1.0))
    assert start == pytest.approx(end, rel=0.02)


# --- active treatment ---------------------------------------------------------

def test_a_scaled_active_word_makes_the_card_heavier(tmp_path):
    plain = ink(frame(tmp_path, base(reveal="karaoke"), "p.png", visible=3, active=1))
    bumped = ink(frame(tmp_path, base(reveal="karaoke", active="scale", active_scale=1.5),
                       "b.png", visible=3, active=1))
    assert bumped > plain


def test_a_marker_bar_paints_behind_the_active_word(tmp_path):
    p = base(reveal="karaoke", active="marker", active_box_hex="#22C55E")
    assert has_colour(frame(tmp_path, p, "m.png", visible=3, active=1), (34, 197, 94))


def test_no_marker_when_the_axis_is_off(tmp_path):
    p = base(reveal="karaoke", active="colour", active_box_hex="#22C55E")
    assert not has_colour(frame(tmp_path, p, "m.png", visible=3, active=1), (34, 197, 94))


# --- decoration ---------------------------------------------------------------

def test_a_box_fills_behind_the_whole_card(tmp_path):
    boxed = ink(frame(tmp_path, base(decor="box", box_hex="#000000"), "x.png", visible=3))
    plain = ink(frame(tmp_path, base(decor="none"), "y.png", visible=3))
    assert boxed > plain * 3


def test_a_hard_shadow_lands_offset_from_the_glyphs(tmp_path):
    shadowed = ink(frame(tmp_path, base(decor="shadow_hard", shadow_hex="#FF0000"), "s.png", visible=3))
    plain = ink(frame(tmp_path, base(decor="none"), "p.png", visible=3))
    assert shadowed > plain


def test_pills_cover_less_than_a_full_box(tmp_path):
    pill = ink(frame(tmp_path, base(decor="pill", box_hex="#000000"), "a.png", visible=3))
    box = ink(frame(tmp_path, base(decor="box", box_hex="#000000"), "b.png", visible=3))
    assert pill < box


# --- layout -------------------------------------------------------------------

def test_stacked_words_make_a_taller_narrower_block(tmp_path):
    def bounds(path):
        a = px(path)[:, :, 3]
        r, c = np.nonzero(a)
        return c.max() - c.min(), r.max() - r.min()

    fw, fh = bounds(frame(tmp_path, base(layout="flow"), "f.png", visible=3))
    sw, sh = bounds(frame(tmp_path, base(layout="stack"), "s.png", visible=3))
    assert sh > fh and sw < fw


# --- per-word styles ----------------------------------------------------------
# The caption rewrite made render_frame take one profile for a whole card,
# which silently dropped per-run style lookup: a card mixing a mono body with a
# Didone punch rendered entirely in mono. The old test missed it because it used
# a card with a single run, where runs[0]'s style is the card's style anyway.

MIXED_STYLES = {
    "default": CaptionProfile(present=True, size_pct=0.05, font_category="mono",
                              fill_hex="#FFFFFF", enter="none"),
    "emphasis": CaptionProfile(present=True, size_pct=0.13, font_category="didone",
                               fill_hex="#FFE94A", enter="none"),
}


def test_a_run_is_drawn_in_its_own_style_not_the_card_s(tmp_path):
    from halfheaven.render.captions import render_card

    mixed = [TextRun(text="money"), TextRun(text="SALT", style="emphasis")]
    plain = [TextRun(text="money"), TextRun(text="SALT")]
    a = ink(render_card(CaptionFrame(runs=mixed, duration=0.3), CANVAS, MIXED_STYLES, tmp_path / "m.png"))
    b = ink(render_card(CaptionFrame(runs=plain, duration=0.3), CANVAS, MIXED_STYLES, tmp_path / "p.png"))
    assert a > b * 1.5, "the emphasis run rendered at body size"


def test_an_emphasised_run_uses_its_own_colour(tmp_path):
    from halfheaven.render.captions import render_card

    mixed = [TextRun(text="money"), TextRun(text="SALT", style="emphasis")]
    path = render_card(CaptionFrame(runs=mixed, duration=0.3), CANVAS, MIXED_STYLES, tmp_path / "m.png")
    assert has_colour(path, (255, 233, 74)) and has_colour(path, (255, 255, 255))
