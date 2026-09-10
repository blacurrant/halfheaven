"""Pairing the emphasis face against the body.

Observed in real output: a Bebas Neue body with an Anton punch. Both are heavy
condensed all-caps sans, so the stressed word read as "the same font, bigger
and bolder" rather than as a different voice. Contrast has to happen on an axis
the eye registers - serif against sans, monospace against proportional - not
weight alone, or emphasis just looks like shouting.
"""
import pytest

from halfheaven.render.fonts import CATEGORIES, resolve_font_path
from halfheaven.render.presets import GROUPS, emphasis_face
from halfheaven.schemas import CaptionProfile, StyleProfile
from halfheaven.render.presets import apply_preset


def test_every_category_belongs_to_a_group():
    grouped = {c for members in GROUPS.values() for c in members}
    assert grouped == set(CATEGORIES)


@pytest.mark.parametrize("body", list(CATEGORIES))
def test_the_punch_never_comes_from_the_body_s_own_group(body):
    punch = emphasis_face(body)
    group_of = {c: g for g, members in GROUPS.items() for c in members}
    assert group_of[punch] != group_of[body], f"{body} -> {punch} is the same genre"


@pytest.mark.parametrize("body", list(CATEGORIES))
def test_the_punch_is_a_different_file(body):
    assert resolve_font_path(emphasis_face(body)) != resolve_font_path(body)


def test_a_condensed_body_does_not_get_a_condensed_punch():
    # the exact pairing that shipped and looked wrong
    assert emphasis_face("condensed") not in GROUPS["sans"]


def test_a_serif_body_gets_a_punch_from_outside_the_serifs():
    assert emphasis_face("didone") not in GROUPS["serif"]


# --- restraint ----------------------------------------------------------------

def test_the_punch_is_larger_but_not_absurd():
    out = apply_preset(StyleProfile(captions=CaptionProfile(present=True, size_pct=0.06)), "hormozi")
    ratio = out.emphasis.size_pct / out.captions.size_pct
    assert 1.3 <= ratio <= 1.8, f"punch is {ratio:.1f}x the body"


def test_a_large_body_does_not_produce_a_punch_that_fills_the_frame():
    big = StyleProfile(captions=CaptionProfile(present=True, size_pct=0.11))
    assert apply_preset(big, "stacked").emphasis.size_pct <= 0.16
