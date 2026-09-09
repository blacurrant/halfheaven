"""Rejecting function words as emphasis.

The prompt asks for concrete nouns and numbers, and the model still returned
"that's", "as" and "He". Emphasis sets a word two and a half times larger than
the body, so a stressed conjunction reads as a mistake. The prompt is guidance;
this is the guard.
"""
from halfheaven.models import Word
from halfheaven.plan.emphasis import meaningful_emphasis


def words(*texts):
    return [Word(t, i * 0.1, i * 0.1 + 0.09) for i, t in enumerate(texts)]


SENTENCE = words("That's", "capitalism", "as", "He", "bought", "an", "iPhone", "actually", "money")


def test_a_content_word_is_kept():
    assert meaningful_emphasis([1], SENTENCE) == [1]          # capitalism


def test_a_contraction_of_function_words_is_rejected():
    assert meaningful_emphasis([0], SENTENCE) == []           # That's


def test_a_conjunction_is_rejected():
    assert meaningful_emphasis([2], SENTENCE) == []           # as


def test_a_pronoun_is_rejected_regardless_of_case():
    assert meaningful_emphasis([3], SENTENCE) == []           # He


def test_an_article_is_rejected():
    assert meaningful_emphasis([5], SENTENCE) == []           # an


def test_a_vague_adverb_is_rejected():
    assert meaningful_emphasis([7], SENTENCE) == []           # actually


def test_punctuation_is_stripped_before_judging():
    assert meaningful_emphasis([6], SENTENCE) == [6]          # iPhone


def test_several_indices_keep_only_the_content_words():
    assert meaningful_emphasis([0, 1, 2, 3, 4, 6, 8], SENTENCE) == [1, 4, 6, 8]


def test_order_is_preserved():
    assert meaningful_emphasis([8, 1], SENTENCE) == [1, 8]


def test_a_number_is_always_kept():
    numbered = words("in", "2020", "I", "started")
    assert meaningful_emphasis([1], numbered) == [1]


def test_indices_out_of_range_are_ignored():
    assert meaningful_emphasis([99], SENTENCE) == []
