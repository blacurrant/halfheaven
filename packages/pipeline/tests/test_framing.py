"""Letterbox detection.

Two reasons this matters. It is a strong, cheap style signal - the reference
puts its content in a band with black bars - and colour statistics measured
through those bars would drag the whole grade dark, so framing must be known
before the grade is measured.
"""
import pathlib

import pytest

from halfheaven.analyze.framing import detect_letterbox

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
LETTERBOXED = FIXTURES / "letterboxed_bars_0.1496.mp4"   # 85px bars on a 568px frame
FULL_FRAME = FIXTURES / "three_shots_at_1.0_3.0.mp4"


def test_detects_that_the_video_is_letterboxed():
    assert detect_letterbox(LETTERBOXED).is_letterboxed is True


def test_measures_the_top_bar():
    assert detect_letterbox(LETTERBOXED).top_pct == pytest.approx(0.1496, abs=0.02)


def test_measures_the_bottom_bar():
    assert detect_letterbox(LETTERBOXED).bottom_pct == pytest.approx(0.1496, abs=0.02)


def test_a_full_frame_video_reports_no_bars():
    framing = detect_letterbox(FULL_FRAME)
    assert framing.is_letterboxed is False
    assert framing.top_pct == 0.0 and framing.bottom_pct == 0.0


def test_content_band_excludes_the_bars():
    top, bottom = detect_letterbox(LETTERBOXED).content_rows(568)
    assert top == pytest.approx(85, abs=12)
    assert bottom == pytest.approx(483, abs=12)


def test_full_frame_content_band_is_the_whole_frame():
    assert detect_letterbox(FULL_FRAME).content_rows(568) == (0, 568)
