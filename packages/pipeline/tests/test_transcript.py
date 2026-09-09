"""The word-index -> time-span primitive.

The LLM only ever emits *word indices*; it never sees a timestamp. This module
turns those indices into real time spans using Whisper's word timings, which is
what structurally prevents hallucinated cut points.
"""
import pytest

from halfheaven.plan.transcript import Word, kept_spans


def w(text, start, end):
    return Word(text=text, start=start, end=end)


# Mirrors a real Groq whisper-large-v3-turbo response (see probe in design notes):
# "So the thing is, UM, I was I was gonna say that this actually changes ..."
TRANSCRIPT = [
    w("So", 0.02, 0.20),
    w("the", 0.20, 0.36),
    w("thing", 0.36, 0.58),
    w("is,", 0.58, 0.90),
    w("UM,", 0.90, 1.56),
    w("I", 1.56, 1.68),
    w("was", 1.68, 1.84),
    w("I", 1.84, 1.96),
    w("was", 1.96, 2.12),
    w("gonna", 2.12, 2.34),
    w("say", 2.34, 2.66),
]


def test_no_cuts_yields_one_span_covering_the_whole_transcript():
    assert kept_spans(TRANSCRIPT, cuts=[]) == [(0.02, 2.66)]


def test_cut_in_the_middle_splits_into_two_spans():
    # drop word 4 ("UM,") -> 0.90..1.56 disappears
    assert kept_spans(TRANSCRIPT, cuts=[(4, 5)]) == [(0.02, 0.90), (1.56, 2.66)]


def test_cut_at_the_start_moves_the_first_span_in():
    assert kept_spans(TRANSCRIPT, cuts=[(0, 4)]) == [(0.90, 2.66)]


def test_cut_at_the_end_moves_the_last_span_back():
    assert kept_spans(TRANSCRIPT, cuts=[(9, 11)]) == [(0.02, 2.12)]


def test_adjacent_cuts_merge_into_a_single_gap():
    # drop the filler "UM," and the "I was I was" stutter
    assert kept_spans(TRANSCRIPT, cuts=[(4, 5), (5, 9)]) == [(0.02, 0.90), (2.12, 2.66)]


def test_cutting_everything_yields_no_spans():
    assert kept_spans(TRANSCRIPT, cuts=[(0, 11)]) == []


# --- silence compression ------------------------------------------------------
# The largest pacing lever, and entirely deterministic: Whisper reports the gaps
# between words, so dead air is removed without asking a model anything.

PAUSED = [
    w("one", 0.00, 0.30),
    w("two", 0.30, 0.60),
    w("three", 2.10, 2.40),   # 1.5s of dead air before this word
    w("four", 2.40, 2.70),
]


def test_a_gap_longer_than_max_silence_splits_the_span():
    assert len(kept_spans(PAUSED, cuts=[], max_silence=0.2)) == 2


def test_a_gap_shorter_than_max_silence_is_left_alone():
    assert kept_spans(PAUSED, cuts=[], max_silence=2.0) == [(0.0, 2.7)]


def test_the_retained_pause_equals_max_silence():
    first, second = kept_spans(PAUSED, cuts=[], max_silence=0.2)
    assert first[1] - 0.60 == pytest.approx(0.1)     # half the allowance after
    assert 2.10 - second[0] == pytest.approx(0.1)    # half before
    assert (first[1] - 0.60) + (2.10 - second[0]) == pytest.approx(0.2)


def test_omitting_max_silence_keeps_the_whole_span():
    assert kept_spans(PAUSED, cuts=[]) == [(0.0, 2.7)]


def test_silence_compression_and_cuts_combine():
    spans = kept_spans(PAUSED, cuts=[(1, 2)], max_silence=0.2)
    assert spans[0] == pytest.approx((0.0, 0.30))
