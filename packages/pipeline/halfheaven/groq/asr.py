"""Groq speech-to-text: whisper-large-v3-turbo, verbose_json + word timestamps."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

from halfheaven.models import Word

# Whisper copies the style of its prompt. Left to detect the language, it heard
# a Hinglish creator as English and translated the Hindi ("mehngi gaadi chalata
# hai" became "the car is running"); pinned to English behind a Roman-script
# Hinglish prompt, it writes the Hindi as spoken. The prompt must not borrow
# from any real clip, or a test on that clip grades the prompt rather than the
# model.
HINGLISH_PROMPT = (
    "Hello dosto, aaj main aapko bataunga ki yeh kaise kaam karta hai. "
    "So basically, the idea is simple, bas thoda dhyan dena."
)
# Consecutive prompt words that mark an echo rather than coincidence. Real
# Hinglish speech shares short stretches like "aaj main aapko" with the prompt.
ECHO_RUN = 6
# Share of the plain hearing's words the prompted one must keep to count as the
# same speech. The prompt costs something on English - it wrote a sentence
# nobody said into an English reel - so it is kept only where it replaced what
# was heard. An invented line only adds words, while translated Hindi replaces
# them, so this holds on a short clip where plain similarity would not.
# Measured: English reels 0.994 and 1.000; a Hinglish talking head 0.56 over its
# first 20s, 0.71 whole, and 0.82 even on its mostly English end.
SAME_SPEECH = 0.95


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def choose_hearing(plain: dict[str, Any], prompted: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Of two Whisper responses for the same audio, the one to caption from.

    Without the prompt Whisper translates Hindi into English; with it, it
    writes the Hindi as spoken but may invent a line in English speech or write
    the prompt out. Where the two agree there was no Hindi to rescue.
    """
    heard = prompted.get("text") or ""
    if echoes_prompt(heard, prompt):
        return plain
    words = _tokens(plain.get("text") or "")
    matcher = difflib.SequenceMatcher(None, words, _tokens(heard), autojunk=False)
    kept = sum(block.size for block in matcher.get_matching_blocks()) / max(1, len(words))
    return plain if kept >= SAME_SPEECH else prompted


def echoes_prompt(text: str, prompt: str) -> bool:
    """Whether a transcript contains its prompt written out, not speech.

    large-v3 did this on a Hinglish clip: partway through it stopped
    transcribing and wrote the prompt instead, losing the rest of the audio.
    """
    words, said = _tokens(prompt), " ".join(_tokens(text))
    return any(" ".join(words[i : i + ECHO_RUN]) in said
               for i in range(len(words) - ECHO_RUN + 1))


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
