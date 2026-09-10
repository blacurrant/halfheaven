"""Several clips treated as one take.

Uploading three takes should behave like uploading one long one: the transcript
runs straight through, cuts land wherever they land, and only at the very end
does anything need to know which file a piece came from. That bookkeeping lives
here rather than smeared through the planner, so everything upstream keeps
working on a single clock.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Reel:
    """An ordered run of clips, addressed as one continuous timeline."""

    parts: Sequence[tuple[str, float]]

    @property
    def duration(self) -> float:
        return sum(length for _, length in self.parts)

    def locate(self, at: float) -> tuple[str, float]:
        """The clip holding `at`, and the time within it.

        A moment past the end clamps to the last frame rather than raising:
        rounding at a boundary is normal and should not fail a render.
        """
        elapsed = 0.0
        for source, length in self.parts:
            if at < elapsed + length:
                return source, max(0.0, at - elapsed)
            elapsed += length
        source, length = self.parts[-1]
        return source, length

    def split(self, span: tuple[float, float]) -> list[tuple[str, float, float]]:
        """Break a span at every clip boundary it crosses.

        A cut does not care where one take ends and the next begins, but the
        renderer does - it can only read one file at a time.
        """
        start, end = span
        end = min(end, self.duration)
        if end <= start:
            return []

        pieces: list[tuple[str, float, float]] = []
        elapsed = 0.0
        for source, length in self.parts:
            clip_start, clip_end = elapsed, elapsed + length
            elapsed = clip_end
            if clip_end <= start or clip_start >= end:
                continue
            pieces.append((
                source,
                max(0.0, start - clip_start),
                min(length, end - clip_start),
            ))
        return pieces
