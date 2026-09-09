"""Measuring a video's colour statistics.

Sampled from the content band only. Black bars are not picture, and averaging
them in would darken every grade we derive.
"""
import pathlib

import pytest

from halfheaven.analyze.framing import Framing, detect_letterbox
from halfheaven.analyze.grade import measure_color_stats

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
FULL_FRAME = FIXTURES / "three_shots_at_1.0_3.0.mp4"
LETTERBOXED = FIXTURES / "letterboxed_bars_0.1496.mp4"   # same content, with bars


def test_lightness_is_reported_on_the_lab_scale():
    stats = measure_color_stats(FULL_FRAME)
    assert 0.0 <= stats.mean[0] <= 100.0


def test_spread_is_positive_for_varied_content():
    assert measure_color_stats(FULL_FRAME).std[0] > 1.0


def test_black_bars_drag_the_measurement_dark_when_not_excluded():
    through_bars = measure_color_stats(LETTERBOXED, framing=Framing(0.0, 0.0))
    content_only = measure_color_stats(LETTERBOXED, framing=detect_letterbox(LETTERBOXED))
    assert content_only.mean[0] > through_bars.mean[0]


def test_excluding_the_bars_recovers_the_original_content_statistics():
    # the letterboxed fixture is the full-frame one scaled and padded, so
    # measuring its content band must land close to the original
    original = measure_color_stats(FULL_FRAME)
    recovered = measure_color_stats(LETTERBOXED, framing=detect_letterbox(LETTERBOXED))
    assert recovered.mean[0] == pytest.approx(original.mean[0], abs=6.0)
