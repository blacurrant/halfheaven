"""Grouping surviving words into caption cards.

Deterministic on purpose. Whisper already reports pauses and punctuation, which
is everything phrase-level chunking needs - so this costs nothing, never varies
between runs, and keeps the model's output small enough to be reliable.
"""
from halfheaven.models import Word
from halfheaven.plan.chunking import chunk_captions


def words(*specs):
    return [Word(text, start, end) for text, start, end in specs]


CONTINUOUS = words(
    ("one", 0.0, 0.2), ("two", 0.2, 0.4), ("three", 0.4, 0.6),
    ("four", 0.6, 0.8), ("five", 0.8, 1.0), ("six", 1.0, 1.2),
    ("seven", 1.2, 1.4), ("eight", 1.4, 1.6),
)


def texts(chunks, source):
    return [" ".join(source[i].text for i in c.word_indices) for c in chunks]


def test_cards_never_exceed_the_maximum_word_count():
    chunks = chunk_captions(CONTINUOUS, cuts=[], max_words=3)
    assert all(len(c.word_indices) <= 3 for c in chunks)


def test_every_surviving_word_appears_exactly_once():
    chunks = chunk_captions(CONTINUOUS, cuts=[], max_words=3)
    seen = [i for c in chunks for i in c.word_indices]
    assert sorted(seen) == list(range(len(CONTINUOUS)))


def test_a_long_pause_starts_a_new_card():
    spoken = words(("hello", 0.0, 0.3), ("there", 0.3, 0.6), ("later", 2.0, 2.4))
    assert texts(chunk_captions(spoken, cuts=[], max_words=6), spoken) == ["hello there", "later"]


def test_sentence_punctuation_starts_a_new_card():
    spoken = words(("done.", 0.0, 0.3), ("next", 0.3, 0.6), ("word", 0.6, 0.9))
    assert texts(chunk_captions(spoken, cuts=[], max_words=6), spoken) == ["done.", "next word"]


def test_cut_words_are_never_captioned():
    chunks = chunk_captions(CONTINUOUS, cuts=[(2, 5)], max_words=6)
    seen = {i for c in chunks for i in c.word_indices}
    assert seen.isdisjoint({2, 3, 4})


def test_a_cut_splits_the_card_around_it():
    chunks = chunk_captions(CONTINUOUS, cuts=[(3, 4)], max_words=8)
    assert texts(chunks, CONTINUOUS) == ["one two three", "five six seven eight"]


def test_emphasis_words_mark_their_card():
    chunks = chunk_captions(CONTINUOUS, cuts=[], max_words=3, emphasis_indices=[4])
    emphasised = [c for c in chunks if c.emphasis]
    assert len(emphasised) == 1 and 4 in emphasised[0].word_indices


def test_no_words_yields_no_cards():
    assert chunk_captions([], cuts=[], max_words=3) == []


# --- avoiding fragmented cards -----------------------------------------------
# Observed on real footage: a 0.35s pause threshold split this speaker into
# cards reading 'oh,', 'And', 'notice?'. Short cards are folded back in.


def test_a_short_trailing_card_is_merged_into_the_previous_one():
    spoken = words(("hello", 0.0, 0.3), ("there", 0.3, 0.6), ("oh", 1.2, 1.4))
    chunks = chunk_captions(spoken, cuts=[], max_words=6, min_words=2, pause_break=0.35)
    assert texts(chunks, spoken) == ["hello there oh"]


def test_a_short_card_is_not_merged_past_the_word_limit():
    spoken = words(("a", 0.0, 0.2), ("b", 0.2, 0.4), ("c", 1.0, 1.2))
    chunks = chunk_captions(spoken, cuts=[], max_words=2, min_words=2, pause_break=0.35)
    assert texts(chunks, spoken) == ["a b", "c"]


def test_a_lone_short_card_is_kept_rather_than_dropped():
    spoken = words(("hi", 0.0, 0.3),)
    assert len(chunk_captions(spoken, cuts=[], max_words=6, min_words=2)) == 1
