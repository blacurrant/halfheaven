"""Media probing.

Every downstream stage asks this module what it is dealing with. It must be
honest about a missing audio track rather than guessing, because the entire
speech-driven half of the pipeline switches off on that one boolean.
"""
import pathlib

import pytest

from halfheaven.media.probe import probe

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
THREE_SHOTS = FIXTURES / "three_shots_at_1.0_3.0.mp4"
SILENT = FIXTURES / "silent_no_audio_track.mp4"
WITH_AUDIO = FIXTURES / "with_audio_track.mp4"


def test_reports_duration():
    assert probe(THREE_SHOTS).duration == pytest.approx(4.5, abs=0.05)


def test_reports_frame_size_and_rate():
    info = probe(THREE_SHOTS)
    assert (info.width, info.height) == (320, 568)
    assert info.fps == pytest.approx(30.0)


def test_video_without_an_audio_stream_reports_no_audio():
    assert probe(SILENT).has_audio is False


def test_video_with_an_audio_stream_reports_audio():
    assert probe(WITH_AUDIO).has_audio is True


def test_portrait_video_is_flagged_vertical():
    assert probe(THREE_SHOTS).is_vertical is True


def test_missing_file_raises_rather_than_returning_empty_info():
    with pytest.raises(FileNotFoundError):
        probe(FIXTURES / "does_not_exist.mp4")
