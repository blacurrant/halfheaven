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
from halfheaven.schemas import Canvas, Caption, EditProgram, MusicBed, SfxHit, StyleProfile, VideoClip

DEFAULT_SFX_FAMILY = "whoosh"


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
    music_src: str | None = None


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
        VideoClip(
            src=source,
            start=start,
            end=end,
            scale_to=profile.punch.scale_mean if index in punched else None,
            ease=profile.punch.ease,
        )
        for index, (start, end) in enumerate(spans)
    ]

    captions: list[Caption] = []
    for chunk in decisions.caption_chunks:
        indices = sorted(chunk.word_indices)
        surviving = [i for i in indices if not _is_cut(i, decisions.cuts)]
        if not surviving:
            continue
        start = timeline.to_program(transcript.words[surviving[0]].start)
        end = timeline.to_program(transcript.words[surviving[-1]].end)
        if start is None or end is None or end <= start:
            continue
        captions.append(
            Caption(
                t=start,
                duration=end - start,
                text=" ".join(transcript.words[i].text for i in surviving),
                anchor=profile.captions.anchor,
                anim=profile.captions.anim,
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
