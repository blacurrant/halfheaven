"""The word-index -> time-span primitive.

The LLM only ever emits *word indices*; it never sees a timestamp. This module
turns those indices into real time spans using Whisper's word timings, which is
what structurally prevents hallucinated cut points.
"""
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
