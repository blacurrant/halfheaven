"""Parsing Groq's verbose_json ASR response.

Fixture is a real whisper-large-v3-turbo response, captured live, not a guess
at the schema.
"""
import json
import pathlib

import pytest

from halfheaven.config import Config
from halfheaven.groq.asr import HINGLISH_PROMPT, echoes_prompt, parse_transcript
from halfheaven.groq.client import GroqClient

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


# --- Hinglish ------------------------------------------------------------------
# Left to detect the language, turbo called a Hinglish creator English and
# translated the Hindi: "mehngi gaadi chalata hai" was captioned "the car is
# running". A Roman-script Hinglish prompt keeps the Hindi as spoken.


class Recorder(GroqClient):
    """A client whose transport returns canned responses and remembers each request."""

    def __init__(self, *responses):
        super().__init__(Config(api_key="k", asr_model="whisper-large-v3-turbo",
                                llm_model="m", vision_model="v"))
        self.responses, self.sent = list(responses), []

    def _post(self, path, **kwargs):
        self.sent.append(kwargs["data"])
        return self.responses.pop(0)


def heard(text):
    return {**FIXTURE, "text": text}


def transcribe(tmp_path, plain, prompted):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"")
    client = Recorder(heard(plain), heard(prompted))
    return client, client.transcribe(audio)


def test_hindi_is_kept_as_spoken_rather_than_translated(tmp_path):
    client, transcript = transcribe(
        tmp_path,
        plain="Do you know how money attracts money in real life? In 2020, when I started freelancing",
        prompted="Aapko pata hai money attracts money, real life mein kaise kaam karta hai? "
                 "In 2020, jab main apni freelancing chalu kar raha tha")
    assert transcript.text.startswith("Aapko pata hai")
    assert "prompt" not in client.sent[0]
    assert client.sent[1]["prompt"] == HINGLISH_PROMPT
    # detection is what translated the Hindi; pinning English with a Hinglish
    # prompt transliterates it instead
    assert client.sent[0]["language"] == client.sent[1]["language"] == "en"


def test_english_speech_keeps_the_hearing_without_the_prompt(tmp_path):
    # the prompt is not free: on an English reel it wrote in a sentence nobody
    # said. When the two hearings agree, the speech had no Hindi to rescue.
    said = ("we are taking baby steps so I can understand color grading all the way "
            "through because I am tired of every single tutorial selling a power grade")
    _, transcript = transcribe(
        tmp_path, plain=said,
        prompted=said.replace("understand color", "understand how to color grade. I don't understand color"))
    assert transcript.text == said


def test_a_hearing_that_writes_out_the_prompt_is_discarded(tmp_path):
    # large-v3 did this on the Hinglish clip: two thirds of the way in it
    # stopped transcribing and wrote the prompt out instead
    _, transcript = transcribe(tmp_path, plain="When I got my first car, it was an Audi",
                               prompted="When I got my first " + HINGLISH_PROMPT)
    assert transcript.text == "When I got my first car, it was an Audi"


def test_speech_that_merely_shares_words_with_the_prompt_is_not_an_echo():
    assert not echoes_prompt("aaj main aapko ek kahani sunata hoon", HINGLISH_PROMPT)
    assert echoes_prompt("so " + HINGLISH_PROMPT.upper(), HINGLISH_PROMPT)
