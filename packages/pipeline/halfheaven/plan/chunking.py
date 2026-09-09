"""Grouping surviving words into caption cards.

Deterministic on purpose. Whisper reports pauses and punctuation, which is all
phrase-level chunking needs - so this costs nothing, never varies between runs,
and keeps the editorial model's output small enough to be reliable. The model
is left with the decisions that actually require judgement.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from halfheaven.models import Word
from halfheaven.plan.builder import CaptionChunk

# A gap this long reads as a phrase boundary to a viewer.
PAUSE_BREAK = 0.6
SENTENCE_ENDINGS = (".", "?", "!", "…")


def _is_cut(index: int, cuts: Sequence[tuple[int, int]]) -> bool:
    return any(start <= index < stop for start, stop in cuts)


def chunk_captions(
    words: Sequence[Word],
    cuts: Sequence[tuple[int, int]],
    max_words: int,
    emphasis_indices: Iterable[int] = (),
    pause_break: float = PAUSE_BREAK,
    min_words: int = 1,
) -> list[CaptionChunk]:
    emphasis = set(emphasis_indices)
    chunks: list[CaptionChunk] = []
    current: list[int] = []

    def flush() -> None:
        if current:
            chunks.append(
                CaptionChunk(
                    word_indices=list(current),
                    emphasis=any(i in emphasis for i in current),
                )
            )
            current.clear()

    previous: int | None = None
    for index, word in enumerate(words):
        if _is_cut(index, cuts):
            # A removed span is a hard break: the words either side of it are no
            # longer adjacent in the finished video.
            flush()
            previous = None
            continue

        if previous is not None:
            gap = word.start - words[previous].end
            if gap >= pause_break or words[previous].text.endswith(SENTENCE_ENDINGS):
                flush()

        if len(current) >= max_words:
            flush()

        current.append(index)
        previous = index

    flush()

    # A card of one or two words reads as a flicker. Observed on real footage:
    # cards reading 'oh,', 'And', 'notice?'. Fold them back into the card before,
    # unless that would breach the word limit.
    folded: list[CaptionChunk] = []
    for chunk in chunks:
        if (
            folded
            and len(chunk.word_indices) < min_words
            and len(folded[-1].word_indices) + len(chunk.word_indices) <= max_words
        ):
            previous = folded[-1]
            folded[-1] = CaptionChunk(
                word_indices=previous.word_indices + chunk.word_indices,
                emphasis=previous.emphasis or chunk.emphasis,
            )
        else:
            folded.append(chunk)
    return folded
