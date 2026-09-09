"""Parsing and clamping the editorial model's output.

The model chooses *what* to cut; it never produces a timestamp. Even so its
output is model output, so it is validated before any number is derived from
it. Unusable entries are dropped rather than repaired: a dropped cut gives a
slightly looser edit, a bad one gives a broken video.
"""
from __future__ import annotations

from typing import Any

from halfheaven.plan.builder import CaptionChunk, Decisions


def _clamp_bound(value: Any, n_words: int) -> int | None:
    """A cut range endpoint. Clamping is meaningful here: "to 999" reads as
    "to the end of the transcript"."""
    try:
        return max(0, min(int(value), n_words))
    except (TypeError, ValueError):
        return None


def _exact_index(value: Any, n_words: int) -> int | None:
    """A reference to one specific word. Never clamped - snapping 99 to the
    last word would invent a choice the model did not make."""
    try:
        index = int(value)
    except (TypeError, ValueError):
        return None
    return index if 0 <= index < n_words else None


def _merge_overlapping(
    ranges: list[tuple[int, int]], max_cut_words: int | None
) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, stop in sorted(ranges):
        if merged and start <= merged[-1][1]:
            previous_start, previous_stop = merged[-1]
            combined = (previous_start, max(previous_stop, stop))
            # Merging must not manufacture a cut longer than we would accept.
            if max_cut_words is None or combined[1] - combined[0] <= max_cut_words:
                merged[-1] = combined
                continue
        merged.append((start, stop))
    return merged


def parse_decisions(
    payload: dict[str, Any], *, n_words: int, max_cut_words: int | None = None
) -> Decisions:
    """Validate the editorial model's output.

    `max_cut_words` refuses spans long enough to be content rather than
    disfluency. Observed on real footage: the model removed 34 consecutive
    words of narrative as "rambling". A stutter is short; a paragraph is not.
    """
    cuts: list[tuple[int, int]] = []
    for entry in payload.get("cuts") or []:
        if not isinstance(entry, dict):
            continue
        start = _clamp_bound(entry.get("from"), n_words)
        stop = _clamp_bound(entry.get("to"), n_words)
        if start is None or stop is None or stop <= start:
            continue
        if max_cut_words is not None and stop - start > max_cut_words:
            continue
        cuts.append((start, stop))
    cuts = _merge_overlapping(cuts, max_cut_words)

    if cuts and sum(stop - start for start, stop in cuts) >= n_words:
        raise ValueError("editorial pass cut the entire transcript; nothing would remain")

    chunks: list[CaptionChunk] = []
    for entry in payload.get("captions") or []:
        if not isinstance(entry, dict):
            continue
        words = sorted(
            {i for i in (_exact_index(w, n_words) for w in entry.get("words") or []) if i is not None}
        )
        if not words:
            continue
        chunks.append(CaptionChunk(word_indices=words, emphasis=bool(entry.get("emphasis"))))

    punches = sorted(
        {i for i in (_exact_index(p, n_words) for p in payload.get("punch_ins") or []) if i is not None}
    )

    return Decisions(cuts=cuts, caption_chunks=chunks, punch_word_indices=punches)
