"""Turning editorial decisions into a validated EditProgram.

The deterministic half of planning. The model contributes word indices and
nothing else; every number below is computed from Whisper's measured timings,
so a timing bug can only live here - not in a prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from halfheaven.groq.asr import Transcript
from halfheaven.plan.timeline import Timeline
from halfheaven.plan.transcript import kept_spans
from halfheaven.schemas import (
    Canvas,
    Caption,
    EditProgram,
    MusicBed,
    SfxHit,
    StyleProfile,
    TextRun,
    VideoClip,
)

DEFAULT_SFX_FAMILY = "whoosh"
# Style names the program's style table must define.
BODY_STYLE = "default"
EMPHASIS_STYLE = "emphasis"


@dataclass(frozen=True)
class CaptionChunk:
    """A group of words shown together as one caption card."""

    word_indices: list[int]
    emphasis: bool = False


@dataclass(frozen=True)
class Decisions:
    """Everything the editorial pass decided, expressed only as word indices."""

    cuts: list[tuple[int, int]] = field(default_factory=list)
    caption_chunks: list[CaptionChunk] = field(default_factory=list)
    punch_word_indices: list[int] = field(default_factory=list)
    # Words the speaker stresses. Drives type, not framing - a word can deserve
    # a larger face without deserving a push-in.
    emphasis_word_indices: list[int] = field(default_factory=list)
    music_src: str | None = None


# Framings cycled through, tightest last. Reframing rather than repeating is
# what stops a one-camera take reading as a single held shot.
FRAMINGS: tuple[tuple[float, float], ...] = (
    (1.0, 0.50),    # wide, centred
    (1.16, 0.44),   # medium, drifted left
    (1.08, 0.56),   # slightly in, drifted right
    (1.28, 0.50),   # close, centred
)


def _framing(index: int, total: int, is_punched: bool, profile: StyleProfile) -> dict[str, float]:
    """Scale and crop centre for one segment.

    Deterministic: the same edit reframes the same way every render, so a
    creator who asks for one change does not get a different cut everywhere
    else. A stressed word always takes the tightest framing available.
    """
    if is_punched:
        scale, centre = max(FRAMINGS, key=lambda f: f[0])
        return {"scale_to": max(scale, profile.punch.scale_mean), "crop_x": centre}
    if profile.punch.variety <= 0 or total < 2:
        return {"scale_to": None, "crop_x": 0.5}
    scale, centre = FRAMINGS[index % len(FRAMINGS)]
    # variety eases every framing back toward wide and centred
    eased = 1.0 + (scale - 1.0) * profile.punch.variety
    drift = 0.5 + (centre - 0.5) * profile.punch.variety
    return {"scale_to": eased if eased > 1.0 else None, "crop_x": drift}


def _is_cut(index: int, cuts: list[tuple[int, int]]) -> bool:
    return any(start <= index < stop for start, stop in cuts)


def _evenly_spaced(count: int, total: int) -> list[int]:
    """`count` indices spread across `total`, deterministically."""
    if count <= 0 or total <= 0:
        return []
    if count >= total:
        return list(range(total))
    return [round(i * total / count) for i in range(count)]


def build_program(
    *,
    source: str,
    canvas: Canvas,
    transcript: Transcript,
    profile: StyleProfile,
    decisions: Decisions,
) -> EditProgram:
    spans = kept_spans(transcript.words, decisions.cuts, max_silence=profile.trim.max_silence)
    if not spans:
        raise ValueError("every word was cut; nothing left to build a program from")
    timeline = Timeline(spans)

    # A punch-in belongs to whichever surviving span holds the chosen word.
    punched: set[int] = set()
    for index in decisions.punch_word_indices:
        word = transcript.words[index]
        for span_index, (start, end) in enumerate(spans):
            if start <= word.start <= end:
                punched.add(span_index)
                break

    video = [
        VideoClip(src=source, start=start, end=end, ease=profile.punch.ease,
                  **_framing(index, len(spans), index in punched, profile))
        for index, (start, end) in enumerate(spans)
    ]

    emphasised = set(decisions.emphasis_word_indices)
    captions: list[Caption] = []
    for chunk in decisions.caption_chunks:
        indices = sorted(chunk.word_indices)
        surviving = [i for i in indices if not _is_cut(i, decisions.cuts)]
        if not surviving:
            continue
        end = timeline.to_program(transcript.words[surviving[-1]].end)
        if end is None:
            continue

        # One run per word, timed on the program clock, so the renderer can
        # reveal them in turn and style individual words differently.
        runs: list[TextRun] = []
        for index in surviving:
            word = transcript.words[index]
            moment = timeline.to_program(word.start)
            if moment is None:
                continue
            runs.append(
                TextRun(
                    text=word.text,
                    style=EMPHASIS_STYLE if index in emphasised else BODY_STYLE,
                    t=moment,
                )
            )
        if not runs or end <= runs[0].t:
            continue

        captions.append(
            Caption(
                t=runs[0].t,
                duration=end - runs[0].t,
                runs=runs,
                anchor=profile.captions.anchor,
                emphasis=chunk.emphasis,
            )
        )

    # Seams are the internal joins between clips - where a viewer perceives a cut.
    seams = timeline.seams
    family = profile.sfx.families[0] if profile.sfx.families else DEFAULT_SFX_FAMILY
    chosen = _evenly_spaced(round(profile.sfx.rate_at_cuts * len(seams)), len(seams))
    sfx = [SfxHit(t=seams[i], family=family) for i in chosen]

    music = None
    if profile.music.present and decisions.music_src:
        music = MusicBed(
            src=decisions.music_src,
            gain_db=profile.music.gain_db,
            duck_db=profile.music.duck_db,
        )

    return EditProgram(canvas=canvas, video=video, captions=captions, sfx=sfx, music=music)
