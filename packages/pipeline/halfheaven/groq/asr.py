"""Groq speech-to-text: whisper-large-v3-turbo, verbose_json + word timestamps."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from halfheaven.models import Word


@dataclass(frozen=True)
class Transcript:
    words: list[Word]
    text: str = ""
    duration: float = 0.0
    language: str = ""

    def numbered(self) -> str:
        """The transcript as the LLM sees it: index-tagged words, no timings.

        Withholding timestamps is the point. The model cannot emit a cut point
        we did not measure if it never sees one.
        """
        return " ".join(f"[{i}] {w.text}" for i, w in enumerate(self.words))


def parse_transcript(payload: dict[str, Any]) -> Transcript:
    words = [
        Word(text=w["word"].strip(), start=float(w["start"]), end=float(w["end"]))
        for w in payload.get("words") or []
    ]
    return Transcript(
        words=words,
        text=(payload.get("text") or "").strip(),
        duration=float(payload.get("duration") or 0.0),
        language=payload.get("language") or "",
    )
