"""Parsing Groq's verbose_json ASR response.

Fixture is a real whisper-large-v3-turbo response, captured live, not a guess
at the schema.
"""
import json
import pathlib

import pytest

from halfheaven.groq.asr import parse_transcript

FIXTURE = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "groq_whisper_verbose_json.json").read_text()
)


@pytest.fixture
def transcript():
    return parse_transcript(FIXTURE)


def test_every_word_is_parsed(transcript):
    assert len(transcript.words) == 20


def test_word_carries_text_and_timings(transcript):
    first = transcript.words[0]
    assert first.text == "So"
    assert first.start == pytest.approx(0.02)
    assert first.end == pytest.approx(0.20)


def test_duration_comes_from_the_response(transcript):
    assert transcript.duration == pytest.approx(5.915, abs=0.01)


def test_filler_word_survives_as_its_own_index(transcript):
    # the LLM cuts by index, so "UM," must not be merged into a neighbour
    assert transcript.words[4].text == "UM,"


def test_numbered_words_render_back_to_a_prompt_the_llm_can_cut_against(transcript):
    # what we actually send the model: index-tagged words, no timestamps at all
    numbered = transcript.numbered()
    assert numbered.startswith("[0] So [1] the [2] thing [3] is, [4] UM,")
    assert ":" not in numbered  # no timestamps leak to the model
