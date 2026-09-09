"""Word-index -> time-span mapping.

The LLM emits word indices, never timestamps. This module is the only place
those indices become seconds, which is what structurally prevents the model
from inventing a cut point that does not correspond to real speech.
"""
from __future__ import annotations

from typing import Sequence

from halfheaven.models import Span, Word

__all__ = ["Word", "Span", "kept_spans"]


def _surviving_runs(count: int, cuts: Sequence[tuple[int, int]]) -> list[list[int]]:
    """Consecutive word indices that no cut removes."""
    dropped = [False] * count
    for start, stop in cuts:
        for i in range(max(0, start), min(count, stop)):
            dropped[i] = True

    runs: list[list[int]] = []
    current: list[int] = []
    for index, is_dropped in enumerate(dropped):
        if is_dropped:
            if current:
                runs.append(current)
                current = []
        else:
            current.append(index)
    if current:
        runs.append(current)
    return runs


def kept_spans(
    words: Sequence[Word],
    cuts: Sequence[tuple[int, int]],
    max_silence: float | None = None,
) -> list[Span]:
    """Time spans that survive `cuts`, with long pauses compressed.

    `cuts` are half-open word-index ranges, `[a, b)`. They may overlap, sit out
    of order, or run past the ends of the transcript; all are clamped. Runs of
    surviving words collapse into one span, so adjacent cuts produce one gap
    rather than a zero-length seam.

    `max_silence` caps the pause between consecutive words. A longer gap splits
    the span, keeping half the allowance on each side so the join lands in dead
    air instead of clipping the speech either side of it. This is the largest
    pacing lever in the system and it needs no model at all - Whisper already
    measured every gap.
    """
    if not words:
        return []

    spans: list[Span] = []
    for run in _surviving_runs(len(words), cuts):
        span_start = words[run[0]].start
        previous = run[0]
        for index in run[1:]:
            gap = words[index].start - words[previous].end
            if max_silence is not None and gap > max_silence:
                allowance = max_silence / 2
                spans.append((span_start, words[previous].end + allowance))
                span_start = words[index].start - allowance
            previous = index
        spans.append((span_start, words[previous].end))
    return spans
