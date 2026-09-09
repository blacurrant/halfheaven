"""Telling burned-in graphics apart from filmed text.

On real footage the largest text-like region is usually not the caption - it is
a street sign, a station board, an inset. The property that actually separates
an overlay from filmed content is that the overlay holds its position across
cuts while everything behind it changes.
"""
import pathlib

import pytest

from halfheaven.analyze.text_regions import detect_persistent_caption

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
WITH_TITLE = FIXTURES / "persistent_title_over_three_shots.mp4"   # title at y=400/568
NO_TITLE = FIXTURES / "three_shots_at_1.0_3.0.mp4"


def test_finds_the_persistent_title():
    assert detect_persistent_caption(WITH_TITLE) is not None


def test_ignores_per_shot_scenery_text_and_locks_onto_the_overlay():
    # 'PLATFORM 6' sits at y~0.08 in shot 1 and 'EXPRESS' at y~0.83 in shot 2;
    # only 'THREE DAYS' at y~0.74 is present in every shot.
    box = detect_persistent_caption(WITH_TITLE)
    assert box.center_y_pct == pytest.approx(0.74, abs=0.06)


def test_the_overlay_is_horizontally_centred():
    assert detect_persistent_caption(WITH_TITLE).center_x_pct == pytest.approx(0.50, abs=0.06)


def test_video_with_no_overlay_returns_nothing():
    assert detect_persistent_caption(NO_TITLE) is None
