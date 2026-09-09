"""Extracting an audio track for transcription.

Sent to Groq as audio rather than video: a 60s clip becomes a few hundred KB
instead of tens of MB, which keeps every request well inside the upload limit.
"""
import pathlib

import pytest

from halfheaven.media.audio import extract_audio
from halfheaven.media.probe import probe

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
WITH_AUDIO = FIXTURES / "with_audio_track.mp4"
SILENT = FIXTURES / "silent_no_audio_track.mp4"


def test_extracts_a_playable_audio_file(tmp_path):
    out = extract_audio(WITH_AUDIO, tmp_path / "a.wav")
    assert out.exists() and out.stat().st_size > 0


def test_extracted_audio_keeps_the_source_duration(tmp_path):
    out = extract_audio(WITH_AUDIO, tmp_path / "a.wav")
    assert probe(WITH_AUDIO).duration == pytest.approx(3.0, abs=0.1)
    assert out.stat().st_size > 16000  # 3s of 16kHz mono pcm is ~96KB


def test_video_without_audio_raises_rather_than_writing_a_silent_file(tmp_path):
    # both original sample videos had no audio; a silent wav would transcribe
    # to nothing and look like a model failure instead of a missing track
    with pytest.raises(ValueError):
        extract_audio(SILENT, tmp_path / "a.wav")
