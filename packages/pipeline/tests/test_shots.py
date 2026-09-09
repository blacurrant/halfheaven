"""Shot detection and pacing extraction.

Pacing is the most recoverable and most distinctive part of an editing style,
so this is the backbone of the StyleProfile. Asserted against a fixture whose
cut points are known exactly, not eyeballed.
"""
import pathlib

import pytest

from halfheaven.analyze.shots import detect_shots, pacing

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
THREE_SHOTS = FIXTURES / "three_shots_at_1.0_3.0.mp4"   # cuts at 1.0s and 3.0s, 4.5s total
CONTINUOUS = FIXTURES / "silent_no_audio_track.mp4"      # one unbroken 3.0s take


def test_finds_every_shot():
    assert len(detect_shots(THREE_SHOTS)) == 3


def test_shot_boundaries_land_on_the_real_cuts():
    boundaries = [round(s.start, 2) for s in detect_shots(THREE_SHOTS)[1:]]
    assert boundaries == pytest.approx([1.0, 3.0], abs=0.1)


def test_shot_durations_match_the_source_clips():
    durations = [s.duration for s in detect_shots(THREE_SHOTS)]
    assert durations == pytest.approx([1.0, 2.0, 1.5], abs=0.1)


def test_a_continuous_take_is_one_shot_not_zero():
    # scenedetect returns an empty list when it finds no cuts; a video is
    # always at least one shot, and downstream pacing maths divides by count.
    shots = detect_shots(CONTINUOUS)
    assert len(shots) == 1
    assert shots[0].duration == pytest.approx(3.0, abs=0.1)


def test_pacing_reports_median_shot_length():
    assert pacing(detect_shots(THREE_SHOTS)).median_shot == pytest.approx(1.5, abs=0.1)


def test_pacing_reports_cuts_per_minute():
    # 2 cuts across 4.5s -> 26.7 cuts/min
    assert pacing(detect_shots(THREE_SHOTS)).cuts_per_min == pytest.approx(26.7, abs=0.5)


def test_a_continuous_take_has_no_cuts_per_minute():
    assert pacing(detect_shots(CONTINUOUS)).cuts_per_min == pytest.approx(0.0)
