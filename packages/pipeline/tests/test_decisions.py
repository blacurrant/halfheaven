"""Validating the editorial model's output.

The model is trusted to choose *what* to cut and nothing else. Its output is
still model output, so it is clamped and checked before a single number is
derived from it. Anything unusable is dropped rather than allowed to corrupt
the program - a dropped cut yields a slightly looser edit, a bad one yields a
broken video.
"""
import pytest

from halfheaven.plan.decisions import parse_decisions

N_WORDS = 11


def parse(payload):
    return parse_decisions(payload, n_words=N_WORDS)


def test_valid_cuts_are_kept():
    assert parse({"cuts": [{"from": 4, "to": 5}]}).cuts == [(4, 5)]


def test_indices_past_the_end_of_the_transcript_are_clamped():
    assert parse({"cuts": [{"from": 9, "to": 999}]}).cuts == [(9, 11)]


def test_negative_indices_are_clamped():
    assert parse({"cuts": [{"from": -5, "to": 2}]}).cuts == [(0, 2)]


def test_reversed_range_is_dropped():
    assert parse({"cuts": [{"from": 7, "to": 3}]}).cuts == []


def test_empty_range_is_dropped():
    assert parse({"cuts": [{"from": 3, "to": 3}]}).cuts == []


def test_overlapping_cuts_are_merged():
    assert parse({"cuts": [{"from": 2, "to": 6}, {"from": 4, "to": 8}]}).cuts == [(2, 8)]


def test_cuts_are_returned_in_order():
    assert parse({"cuts": [{"from": 8, "to": 10}, {"from": 1, "to": 3}]}).cuts == [(1, 3), (8, 10)]


def test_a_cut_removing_the_entire_transcript_is_rejected():
    # nothing would be left to render
    with pytest.raises(ValueError):
        parse({"cuts": [{"from": 0, "to": 11}]})


def test_malformed_entries_are_skipped_not_fatal():
    payload = {"cuts": [{"from": "x", "to": 5}, {"nope": 1}, {"from": 4, "to": 5}]}
    assert parse(payload).cuts == [(4, 5)]


def test_missing_keys_yield_no_decisions():
    decisions = parse({})
    assert decisions.cuts == [] and decisions.caption_chunks == [] and decisions.punch_word_indices == []


def test_caption_chunks_are_parsed_with_their_emphasis_flag():
    chunks = parse({"captions": [{"words": [0, 1, 2], "emphasis": True}]}).caption_chunks
    assert chunks[0].word_indices == [0, 1, 2] and chunks[0].emphasis is True


def test_caption_chunk_indices_outside_the_transcript_are_dropped():
    chunks = parse({"captions": [{"words": [9, 10, 42]}]}).caption_chunks
    assert chunks[0].word_indices == [9, 10]


def test_caption_chunk_with_no_valid_words_is_dropped():
    assert parse({"captions": [{"words": [99, 100]}]}).caption_chunks == []


def test_punch_indices_outside_the_transcript_are_dropped():
    assert parse({"punch_ins": [3, 999, -1]}).punch_word_indices == [3]


# --- guarding against over-cutting -------------------------------------------
# Observed on real footage: the model removed 34 consecutive words of narrative
# ("In 2020, when I started freelancing...") as "rambling". Disfluency is short;
# a long span is the model deleting content, so long cuts are refused.


def test_a_cut_longer_than_the_limit_is_dropped():
    payload = {"cuts": [{"from": 10, "to": 44, "kind": "ramble"}]}
    assert parse_decisions(payload, n_words=239, max_cut_words=8).cuts == []


def test_a_cut_at_the_limit_is_kept():
    payload = {"cuts": [{"from": 10, "to": 18}]}
    assert parse_decisions(payload, n_words=239, max_cut_words=8).cuts == [(10, 18)]


def test_short_cuts_survive_alongside_a_rejected_long_one():
    payload = {"cuts": [{"from": 4, "to": 5}, {"from": 10, "to": 44}]}
    assert parse_decisions(payload, n_words=239, max_cut_words=8).cuts == [(4, 5)]


def test_merging_never_creates_a_cut_beyond_the_limit():
    # two adjacent short cuts must not merge into one long one
    payload = {"cuts": [{"from": 10, "to": 17}, {"from": 16, "to": 24}]}
    assert parse_decisions(payload, n_words=239, max_cut_words=8).cuts == [(10, 17), (16, 24)]


# --- emphasis ----------------------------------------------------------------
# Separate from punch-ins on purpose: a word can deserve a larger typeface
# without deserving a camera push-in, and vice versa.


def test_emphasis_words_are_parsed():
    assert parse_decisions({"emphasis": [2, 7]}, n_words=N_WORDS).emphasis_word_indices == [2, 7]


def test_emphasis_indices_outside_the_transcript_are_dropped():
    assert parse_decisions({"emphasis": [3, 999, -1]}, n_words=N_WORDS).emphasis_word_indices == [3]


def test_duplicate_emphasis_indices_collapse():
    assert parse_decisions({"emphasis": [4, 4, 4]}, n_words=N_WORDS).emphasis_word_indices == [4]


def test_no_emphasis_key_yields_none():
    assert parse_decisions({}, n_words=N_WORDS).emphasis_word_indices == []


def test_emphasis_is_independent_of_punch_ins():
    decisions = parse_decisions({"emphasis": [2], "punch_ins": [8]}, n_words=N_WORDS)
    assert decisions.emphasis_word_indices == [2] and decisions.punch_word_indices == [8]
