"""Deciding which words may carry emphasis.

The editorial prompt asks for concrete nouns and numbers; the model still
returned "that's", "as" and "He". Emphasis renders a word about two and a half
times the body size in a different face, so a stressed conjunction reads as a
mistake rather than as emphasis. The prompt is guidance; this is the guard.

English-only, which is a real limitation: a mixed-language transcript will pass
its non-English function words through. Better to under-filter than to reject
content words we do not recognise.
"""
from __future__ import annotations

import string
from typing import Iterable, Sequence

from halfheaven.models import Word

# Function words plus hedges and intensifiers that carry no visual meaning.
FUNCTION_WORDS = frozenset(
    """
    a an the this that these those there here
    i me my mine we us our ours you your yours he him his she her hers it its
    they them their theirs who whom whose what which
    am is are was were be been being do does did doing have has had having
    will would shall should can could may might must
    and or but nor for yet so as if then than because while when where
    of in on at to from by with about into over after before under
    not no nor too very just really actually basically literally
    like well okay ok now already still also even much many some any
    one thing things way ways lot lots kind sort
    """.split()
)

MIN_LENGTH = 3


def _core(text: str) -> str:
    """The word itself: no punctuation, no case, no possessive or contraction."""
    stripped = text.strip(string.punctuation + "’“”").lower()
    for suffix in ("'s", "’s", "n't", "’t", "'re", "'ll", "'ve", "'d", "'m"):
        if stripped.endswith(suffix):
            stripped = stripped[: -len(suffix)]
    return stripped


def is_meaningful(text: str) -> bool:
    core = _core(text)
    if not core:
        return False
    if any(character.isdigit() for character in core):
        return True  # numbers are always worth stressing
    if len(core) < MIN_LENGTH:
        return False
    if core in FUNCTION_WORDS:
        return False
    # A contraction of two function words ("that's", "it's") reduces to one.
    return True


def meaningful_emphasis(indices: Iterable[int], words: Sequence[Word]) -> list[int]:
    """The subset of `indices` whose words can carry emphasis, in order."""
    return [
        index
        for index in sorted(set(indices))
        if 0 <= index < len(words) and is_meaningful(words[index].text)
    ]
