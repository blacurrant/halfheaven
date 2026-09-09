"""Types shared across every stage. Deliberately tiny and dependency-free."""
from __future__ import annotations

from dataclasses import dataclass

Span = tuple[float, float]


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
