"""The named looks, composed from the axes.

If these were separate renderers we would have six things to maintain. As
presets they are six dictionaries, and a new one costs nothing.
"""
import numpy as np
import pytest
from PIL import Image

from halfheaven.render.caption_frames import CaptionFrame
from halfheaven.render.captions import render_frame
from halfheaven.render.presets import CAPTION_PRESETS, preset
from halfheaven.schemas import Canvas, TextRun

CANVAS = Canvas(width=360, height=640, fps=30)
WORDS = [TextRun(text="money"), TextRun(text="attracts"), TextRun(text="money")]


def test_the_catalogue_is_not_empty():
    assert len(CAPTION_PRESETS) >= 6


def test_every_preset_builds_a_valid_profile():
    for name in CAPTION_PRESETS:
        assert preset(name).present is True


def test_an_unknown_name_falls_back_rather_than_raising():
    assert preset("no-such-look").present is True


@pytest.mark.parametrize("name", list(CAPTION_PRESETS))
def test_every_preset_renders_something_visible(name, tmp_path):
    path = render_frame(CaptionFrame(runs=WORDS, duration=0.3, active=1),
                        CANVAS, preset(name), tmp_path / f"{name}.png")
    assert (np.array(Image.open(path))[:, :, 3] > 0).sum() > 400


def test_the_presets_are_actually_different_from_each_other(tmp_path):
    seen = {}
    for name in CAPTION_PRESETS:
        path = render_frame(CaptionFrame(runs=WORDS, duration=0.3, active=1),
                            CANVAS, preset(name), tmp_path / f"{name}.png")
        seen[name] = (np.array(Image.open(path))[:, :, 3] > 0).sum()
    # if two looks collapsed onto the same settings their coverage would match
    assert len(set(seen.values())) >= len(seen) - 1, seen


def test_hormozi_marks_the_spoken_word_in_its_own_colour():
    p = preset("hormozi")
    assert p.reveal == "karaoke" and p.active == "colour" and p.all_caps


def test_the_documentary_look_stays_quiet():
    p = preset("documentary")
    assert p.enter == "none" and p.active == "none" and not p.all_caps
