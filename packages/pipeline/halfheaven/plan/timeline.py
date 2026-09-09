"""The program timeline: what the viewer actually sees, after cuts."""
from __future__ import annotations

from typing import Iterable, Sequence

Span = tuple[float, float]


class Timeline:
    """Maps source time onto the finished program's time.

    Built from the kept spans of a single source. Removed gaps have no program
    position at all, so `to_program` returns None for them rather than guessing
    a neighbour - a caller that places a caption in a cut-out gap has a bug, and
    should hear about it rather than get a plausible wrong answer.
    """

    def __init__(self, spans: Iterable[Span]) -> None:
        self.spans: list[Span] = list(spans)
        self._offsets: list[float] = []
        elapsed = 0.0
        for start, end in self.spans:
            self._offsets.append(elapsed)
            elapsed += end - start
        self.duration: float = elapsed

    def to_program(self, source_t: float) -> float | None:
        for (start, end), offset in zip(self.spans, self._offsets):
            if start <= source_t <= end:
                return offset + (source_t - start)
        return None
