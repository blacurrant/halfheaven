"""Choosing a caption look without losing what we measured.

A preset decides structure - how words group, reveal, enter, how the spoken
word is marked, how the text sits on the footage. The reference still decides
colour and position, because those are what make the output resemble the video
the creator pointed at. Picking a look should not throw that away.
"""
import pytest

from halfheaven.render.presets import apply_preset, preset
from halfheaven.schemas import CaptionProfile, StyleProfile

MEASURED = StyleProfile(
    captions=CaptionProfile(present=True, fill_hex="#A4A848", anchor=(0.5, 0.732),
                            font_category="mono", size_pct=0.0617, reveal="append"),
)


def test_the_preset_decides_structure():
    out = apply_preset(MEASURED, "hormozi")
    assert out.captions.reveal == "karaoke"
    assert out.captions.active == "colour"
    assert out.captions.all_caps is True


def test_the_reference_keeps_its_colour():
    assert apply_preset(MEASURED, "hormozi").captions.fill_hex == "#A4A848"


def test_the_reference_keeps_its_position():
    assert apply_preset(MEASURED, "beast").captions.anchor == (0.5, 0.732)


def test_a_look_changes_the_typeface():
    assert apply_preset(MEASURED, "beast").captions.font_category == "display"


def test_an_unmeasured_reference_takes_the_preset_wholesale():
    # nothing measured means nothing worth preserving
    blank = StyleProfile()
    out = apply_preset(blank, "sticker")
    assert out.captions.anchor == preset("sticker").anchor
    assert out.captions.fill_hex == preset("sticker").fill_hex


def test_the_emphasis_face_still_differs_from_the_body():
    out = apply_preset(MEASURED, "hormozi")
    assert out.emphasis.font_category != out.captions.font_category


def test_an_unknown_look_leaves_a_usable_profile():
    assert apply_preset(MEASURED, "nope").captions.present is True


def test_choosing_a_look_does_not_disturb_pacing_or_grade():
    before = MEASURED.model_copy(deep=True)
    out = apply_preset(MEASURED, "stacked")
    assert out.pacing == before.pacing and out.grade == before.grade
