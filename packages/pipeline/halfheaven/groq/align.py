"""Sharpening Whisper's word timings with forced alignment.

Whisper's word times come out of its attention and drift by a syllable or so:
enough for a cut to clip a consonant or a caption to land early. whisperX's
wav2vec2 aligner places each already-known word against the audio itself. Groq
still decides *what* was said, since the Hinglish handling lives there; this
only moves *when*.

Optional. Without the `ml` extra, or if alignment fails, Groq's times stand.
"""
from __future__ import annotations

import contextlib
import dataclasses
import functools
import pathlib
import sys
import wave

import numpy as np

from halfheaven.groq.asr import Transcript
from halfheaven.models import Word

RATE = 16000        # what whisperX's aligner expects, and what extract_audio writes
# A pause this long starts a new alignment window. Short windows keep each pass
# cheap, and a word Whisper misplaced can only move within its own window.
BREAK = 0.6
MAX_WINDOW = 30.0
PAD = 0.3


def windows(words: list[Word], duration: float) -> list[tuple[int, int, float, float]]:
    """Split word indices at pauses into (first, stop, start, end) windows."""
    groups = []
    first = 0
    for i in range(1, len(words) + 1):
        if (i == len(words) or words[i].start - words[i - 1].end > BREAK
                or words[i].end - words[first].start > MAX_WINDOW):
            groups.append((first, i, max(0.0, words[first].start - PAD),
                           min(duration, words[i - 1].end + PAD)))
            first = i
    return groups


def place(words: list[Word], first: int, placed: list[dict]) -> list[Word]:
    """Move words[first:] onto aligned times, keeping any the aligner left untimed.

    A word with no letters the model knows ("2024", "₹500") comes back without
    a time; it keeps Whisper's rather than being dropped.
    """
    out = list(words)
    for i, p in enumerate(placed, start=first):
        if "start" in p and "end" in p:
            out[i] = dataclasses.replace(out[i], start=round(float(p["start"]), 3),
                                         end=round(float(p["end"]), 3))
    return out


@functools.cache
def _model():
    from whisperx.alignment import load_align_model
    return load_align_model("en", "cpu")


def _read(audio: pathlib.Path) -> np.ndarray:
    with wave.open(str(audio)) as handle:
        if handle.getframerate() != RATE or handle.getnchannels() != 1:
            raise ValueError(f"expected {RATE}Hz mono, got {handle.getframerate()}Hz "
                             f"x{handle.getnchannels()}")
        pcm = handle.readframes(handle.getnframes())
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768


def sharpen(transcript: Transcript, audio: pathlib.Path) -> Transcript:
    if not transcript.words:
        return transcript
    try:
        from whisperx.alignment import align
    except ImportError:
        return transcript
    try:
        samples = _read(audio)
        model, metadata = _model()
        words = list(transcript.words)
        # Library chatter goes to stderr: the fingerprint CLI's stdout is JSON.
        with contextlib.redirect_stdout(sys.stderr):
            for first, stop, start, end in windows(words, len(samples) / RATE):
                text = " ".join(w.text for w in words[first:stop])
                result = align([{"text": text, "start": start, "end": end}],
                               model, metadata, samples, "cpu")
                placed = [w for s in result["segments"] for w in s.get("words", [])]
                # The aligner splits on spaces, so the counts agree unless a word
                # held one; then the window keeps Whisper's times.
                if len(placed) == stop - first:
                    words = place(words, first, placed)
    except Exception as error:  # a failed model download must not stop an edit
        print(f"alignment skipped, keeping Whisper timings: {error}", file=sys.stderr)
        return transcript
    return dataclasses.replace(transcript, words=words)
