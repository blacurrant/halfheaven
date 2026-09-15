"""The render must set type the way the extraction measured it.

The failure these guard against is specific and it shipped: the fingerprint
reported italic, colour, size and position, and the render ignored all of it,
falling back to default type whenever the older analyzer saw no subtitle band.
So these assert that what was measured is what gets drawn - down to the face
file, the accent colour, and where each card sits relative to the speaker.
"""
from __future__ import annotations

import copy
import pathlib

import cv2
import numpy as np
import pytest
from PIL import Image

from halfheaven.analyze.fingerprint import _decor_kind, _glyphs, _halo, _slant, _text_masks
from halfheaven.plan.builder import (
    BODY_STYLE,
    EMPHASIS_STYLE,
    _accent_captions,
    _face_band,
    _place_captions,
)
from halfheaven.plan.typography import GLYPH_TO_SIZE, MIN_DUTY, MIN_SIZE, apply_fingerprint
from halfheaven.render.caption_frames import CaptionFrame
from halfheaven.render.captions import render_frame
from halfheaven.render.fonts import BY_FILE, choose, counterpart
from halfheaven.schemas import Canvas, Caption, CaptionProfile, StyleProfile, TextRun, TypePlan, VideoClip


def reading(value, confidence="measured"):
    return {"value": value, "confidence": confidence, "note": ""}


# What the fingerprint measures on the Day 3 reference.
DAY3 = {"text": {
    "duty_cycle": reading(0.51), "size_pct": reading(0.0297),
    "centroid": reading([0.49, 0.39]), "spread": reading(0.20),
    "placement": reading("composed", "inferred"), "fill_hex": reading("#FFFFFF", "inferred"),
    "accent_hex": reading("#AD0918"), "accent_rate": reading(0.27),
    "weight": reading(0.21), "contrast": reading(0.08, "inferred"),
    "italic": reading(False, "inferred"), "all_caps": reading(False, "inferred"),
    "decor": reading("shadow_soft", "inferred"),
}}


# --------------------------------------------------------------------------
# the mapping: measurements become styles
# --------------------------------------------------------------------------


def test_type_comes_from_the_fingerprint_not_the_defaults():
    profile = apply_fingerprint(StyleProfile(), DAY3)
    body = profile.captions
    assert body.font_file == choose(contrast=0.08, italic=False).file
    assert body.size_pct == pytest.approx(0.0297 / GLYPH_TO_SIZE, abs=1e-4)
    assert body.decor == "shadow_soft", "a measured soft shadow must not become the default outline"
    assert 600 <= body.font_weight <= 700
    assert body.anchor == pytest.approx((0.49, 0.39))


def test_the_stressed_word_takes_the_accent_colour_in_a_contrasting_face():
    emphasis = apply_fingerprint(StyleProfile(), DAY3).emphasis
    body_face = choose(contrast=0.08, italic=False)
    assert emphasis.fill_hex == "#AD0918"
    assert emphasis.font_file == counterpart(body_face).file
    assert BY_FILE[emphasis.font_file].genre != body_face.genre
    assert not emphasis.all_caps, "a script in capitals is illegible"


def test_an_italic_reference_gets_an_italic_face():
    italic = copy.deepcopy(DAY3)
    italic["text"]["italic"] = reading(True, "inferred")
    italic["text"]["contrast"] = reading(0.70, "inferred")
    face = BY_FILE[apply_fingerprint(StyleProfile(), italic).captions.font_file]
    assert face.italic and face.genre == "serif"


def test_type_never_shrinks_below_legible():
    tiny = copy.deepcopy(DAY3)
    tiny["text"]["size_pct"] = reading(0.004)
    assert apply_fingerprint(StyleProfile(), tiny).captions.size_pct == MIN_SIZE


def test_a_reference_without_type_leaves_the_profile_alone():
    bare = {"text": {"duty_cycle": reading(None, "absent")}}
    original = StyleProfile()
    assert apply_fingerprint(original, bare) is original


def test_the_plan_carries_how_type_is_used_across_the_edit():
    plan = apply_fingerprint(StyleProfile(), DAY3).type_plan
    assert (plan.placement, plan.duty_cycle, plan.accent_rate) == ("composed", 0.51, 0.27)
    sparse = copy.deepcopy(DAY3)
    sparse["text"]["duty_cycle"] = reading(0.10)
    assert apply_fingerprint(StyleProfile(), sparse).type_plan.duty_cycle == MIN_DUTY


# --------------------------------------------------------------------------
# the planner: how much type, how often it turns colour, and where it sits
# --------------------------------------------------------------------------


def _card(t: float, words: str, stressed: int | None = None, duration: float = 1.0) -> Caption:
    runs = [TextRun(text=word, style=EMPHASIS_STYLE if i == stressed else BODY_STYLE, t=t + 0.1 * i)
            for i, word in enumerate(words.split())]
    return Caption(t=t, duration=duration, runs=runs)


def test_the_accent_lands_on_the_measured_share_of_cards_and_on_the_longest_word():
    cards = [_card(float(i), "a remarkable day") for i in range(10)]
    stressed = [c for c in _accent_captions(cards, 0.3)
                if any(r.style == EMPHASIS_STYLE for r in c.runs)]
    assert len(stressed) == 3
    assert all(next(r for r in c.runs if r.style == EMPHASIS_STYLE).text == "remarkable"
               for c in stressed)


def test_composed_type_moves_around_the_frame_and_fixed_type_does_not():
    cards = [_card(float(i), "one two") for i in range(6)]
    video = [VideoClip(src="x.mp4", start=0, end=6)]
    composed = TypePlan(placement="composed", centroid=(0.5, 0.2), spread=0.2)
    fixed = TypePlan(placement="fixed", centroid=(0.5, 0.2), spread=0.2)
    assert len({c.anchor for c in _place_captions(cards, composed, video, 0.04)}) >= 4
    assert len({c.anchor for c in _place_captions(cards, fixed, video, 0.04)}) == 1


def test_a_card_is_never_placed_over_the_face():
    cards = [_card(float(i), "one two three") for i in range(9)]
    # the speaker's face was located, so the framing carries it
    video = [VideoClip(src="x.mp4", start=0, end=9, crop_x=0.5, crop_y=0.51)]
    low, high = _face_band(video[0])
    plan = TypePlan(placement="composed", centroid=(0.49, 0.42), spread=0.2)
    size = 0.043
    for card in _place_captions(cards, plan, video, size):
        half = size * 1.25 / 2
        assert card.anchor[1] + half <= low or card.anchor[1] - half >= high, card.anchor


# --------------------------------------------------------------------------
# the renderer draws the chosen face, and the fingerprint reads treatment
# --------------------------------------------------------------------------

CANVAS = Canvas(width=720, height=1280, fps=30)
LINE = CaptionFrame(runs=[TextRun(text=w) for w in "Handling the brand".split()], duration=1.0)


def _drawn(tmp_path, profile: CaptionProfile, tag: str, background: int | np.ndarray = 40) -> np.ndarray:
    rgba = np.array(Image.open(render_frame(LINE, CANVAS, profile, tmp_path / f"{tag}.png"))
                    .convert("RGBA")).astype(float)
    alpha = rgba[:, :, 3:4] / 255.0
    ground = background if isinstance(background, np.ndarray) else np.full_like(rgba[:, :, :3], background)
    return cv2.cvtColor((rgba[:, :, :3] * alpha + ground * (1 - alpha)).astype(np.uint8),
                        cv2.COLOR_RGB2BGR)


def test_a_chosen_face_file_is_the_face_that_gets_drawn(tmp_path):
    """Loading by category alone is why a measured italic rendered upright."""
    def lean(profile, tag):
        glyph, _, labels, kept = _glyphs(*_text_masks(_drawn(tmp_path, profile, tag)))
        return _slant(glyph, labels, kept)
    base = dict(present=True, size_pct=0.07, decor="none", anchor=(0.5, 0.5))
    assert lean(CaptionProfile(**base, font_file="PlayfairDisplay-Italic.ttf"), "italic") > 0.12
    assert abs(lean(CaptionProfile(**base, font_category="didone"), "roman")) < 0.06


def test_a_card_near_the_edge_stays_inside_the_frame(tmp_path):
    frame = _drawn(tmp_path, CaptionProfile(present=True, size_pct=0.07, decor="none",
                                            anchor=(0.97, 0.5)), "edge")
    ys, xs = np.nonzero(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) > 200)
    assert xs.max() < CANVAS.width - 4, "the line ran off the right edge"


@pytest.mark.parametrize("decor", ["stroke", "shadow_soft", "shadow_hard", "none"])
def test_the_fingerprint_reads_a_caption_treatment_back(tmp_path, decor):
    texture = cv2.GaussianBlur(np.random.default_rng(0).integers(90, 150, (1280, 720, 3))
                               .astype(np.uint8), (0, 0), 6).astype(float)
    frame = _drawn(tmp_path, CaptionProfile(present=True, size_pct=0.06, decor=decor,
                                            fill_hex="#FFFFFF", anchor=(0.5, 0.5)), decor, texture)
    glyph, _, _, _ = _glyphs(*_text_masks(frame))
    assert _decor_kind(*_halo(frame, glyph)) == decor


def test_a_shadow_on_a_dark_ground_abstains_rather_than_voting_none(tmp_path):
    """On Day 3's maroon cards a dark shadow is invisible; those frames used to
    outvote the sky frames and turn a soft drop shadow into "none"."""
    frame = _drawn(tmp_path, CaptionProfile(present=True, size_pct=0.06, decor="shadow_soft",
                                            fill_hex="#FFFFFF", anchor=(0.5, 0.5)), "dark", 30)
    glyph, _, _, _ = _glyphs(*_text_masks(frame))
    assert _halo(frame, glyph) is None


def test_an_unjudged_treatment_falls_back_to_a_soft_shadow_not_an_outline():
    unjudged = copy.deepcopy(DAY3)
    unjudged["text"]["decor"] = reading(None, "absent")
    assert apply_fingerprint(StyleProfile(), unjudged).captions.decor == "shadow_soft"


def test_the_grade_comes_from_photography_not_from_title_cards():
    """The older analyzer averaged Day 3's maroon cards into its colour (a* +8.2)
    and tinted the target's skin; the fingerprint measured photography only."""
    graded = copy.deepcopy(DAY3)
    graded["grade"] = {"lab_mean": reading([50.5, 0.4, -4.0]), "lab_std": reading([27.2, 5.0, 12.5])}
    grade = apply_fingerprint(StyleProfile(), graded).grade
    assert grade.measured and grade.lab_mean == pytest.approx((50.5, 0.4, -4.0))
    assert grade.lab_std == pytest.approx((27.2, 5.0, 12.5))


def test_the_stressed_word_never_gets_a_hairline_script():
    """Sacramento's stroke is 4% of its size; on Day 3 it set the stressed word
    as a hairline that broke up on video. A script has to survive caption size."""
    from halfheaven.render.fonts import MIN_ACCENT_STROKE
    for contrast in (0.02, 0.05, 0.08, 0.12, 0.40, 0.70):
        partner = counterpart(choose(contrast=contrast, italic=False))
        assert partner.stroke >= MIN_ACCENT_STROKE, partner.file


def test_the_stressed_word_stands_at_least_as_tall_as_the_body():
    """At a flat 1.25x, a small-bodied script came out shorter than the words
    around it - stressed in colour, demoted in size."""
    profile = apply_fingerprint(StyleProfile(), DAY3)
    body, stressed = BY_FILE[profile.captions.font_file], BY_FILE[profile.emphasis.font_file]
    assert profile.emphasis.size_pct * stressed.x_height >= profile.captions.size_pct * body.x_height

