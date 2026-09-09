"""Word-index -> time-span mapping.

The LLM emits word indices, never timestamps. This module is the only place
those indices become seconds, which is what structurally prevents the model
from inventing a cut point that does not correspond to real speech.
"""
from __future__ import annotations

from typing import Sequence

from halfheaven.models import Span, Word

__all__ = ["Word", "Span", "kept_spans"]


def kept_spans(words: Sequence[Word], cuts: Sequence[tuple[int, int]]) -> list[Span]:
    """Time spans that survive `cuts`.

    `cuts` are half-open word-index ranges, `[a, b)`. They may overlap, sit out
    of order, or run past the ends of the transcript; all are clamped. Runs of
    surviving words collapse into one span, so adjacent cuts produce one gap
    rather than a zero-length seam.
    """
    if not words:
        return []

    dropped = [False] * len(words)
    for start, stop in cuts:
        for i in range(max(0, start), min(len(words), stop)):
            dropped[i] = True

    spans: list[Span] = []
    run_start: int | None = None
    for i, is_dropped in enumerate(dropped):
        if is_dropped:
            if run_start is not None:
                spans.append((words[run_start].start, words[i - 1].end))
                run_start = None
        elif run_start is None:
            run_start = i
    if run_start is not None:
        spans.append((words[run_start].start, words[-1].end))
    return spans
