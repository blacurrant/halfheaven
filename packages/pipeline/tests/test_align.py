"""Forced alignment only moves words; it never drops or reorders them."""
from halfheaven.groq.align import place, windows
from halfheaven.models import Word


def w(text, start, end):
    return Word(text=text, start=start, end=end)


WORDS = [w("so", 0.0, 0.2), w("the", 0.2, 0.4), w("thing", 1.5, 1.8), w("is", 1.8, 2.0)]


def test_windows_split_at_pauses_and_pad_within_the_audio():
    assert windows(WORDS, duration=2.1) == [(0, 2, 0.0, 0.7), (2, 4, 1.2, 2.1)]


def test_untimed_words_keep_whisper_times():
    placed = [{"word": "thing", "start": 1.55, "end": 1.75}, {"word": "is"}]
    out = place(WORDS, 2, placed)
    assert out[:2] == WORDS[:2]
    assert (out[2].start, out[2].end) == (1.55, 1.75)
    assert out[3] == WORDS[3]
