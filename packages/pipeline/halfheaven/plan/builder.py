"""Turning editorial decisions into a validated EditProgram.

The deterministic half of planning. The model contributes word indices and
nothing else; every number below is computed from Whisper's measured timings,
so a timing bug can only live here - not in a prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from halfheaven.groq.asr import Transcript
from halfheaven.models import Span
from halfheaven.plan.reel import Reel
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
# A framing held for less than this reads as a twitch rather than a shot.
MIN_HOLD = 2.0
MAX_HOLD = 9.0


def _framings(
    spans: list[Span], punched: set[int], profile: StyleProfile,
    track: list[float] | None = None,
) -> list[dict[str, float | None]]:
    """A framing for each segment, changing only as often as the style implies.

    How long to hold is not a guess: the reference already told us how long it
    holds a shot. Sixteen reframes in a minute reads as nervous, and it was the
    measured pacing - previously unused - that said so.

    Deterministic, so a creator who asks for one change does not get a
    different cut everywhere else.
    """
    def centre_for(index: int, fallback: float) -> float:
        # a tracked position always wins: it is where the subject actually is,
        # and on a wide source a patterned drift would crop them out
        if track and index < len(track):
            return float(min(1.0, max(0.0, track[index])))
        return fallback

    if profile.punch.variety <= 0 or len(spans) < 2:
        return [
            {"scale_to": FRAMINGS[-1][0] if i in punched else None,
             "crop_x": centre_for(i, 0.5)}
            for i in range(len(spans))
        ]

    hold = min(MAX_HOLD, max(MIN_HOLD, profile.pacing.median_shot or MIN_HOLD))
    variety = profile.punch.variety

    out: list[dict[str, float | None]] = []
    choice = 0
    since = 0.0
    for index, (start, end) in enumerate(spans):
        if index in punched:
            # a stressed word takes the tightest framing wherever it lands
            scale, centre = max(FRAMINGS, key=lambda f: f[0])
            out.append({"scale_to": max(scale, profile.punch.scale_mean),
                        "crop_x": centre_for(index, centre)})
            since = 0.0
            choice = (choice + 1) % len(FRAMINGS)
            continue

        if since >= hold and index > 0:
            choice = (choice + 1) % len(FRAMINGS)
            since = 0.0

        scale, centre = FRAMINGS[choice]
        eased = 1.0 + (scale - 1.0) * variety
        out.append({
            "scale_to": eased if eased > 1.001 else None,
            "crop_x": centre_for(index, 0.5 + (centre - 0.5) * variety),
        })
        since += end - start

    return out


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
    tracker: Callable[[list[Span]], list[float]] | None = None,
    reel: Reel | None = None,
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

    # The tracker runs here because only now do we know where the cuts fell.
    track = tracker(spans) if tracker else None
    framings = _framings(spans, punched, profile, track)

    # A span may cross from one take into the next. The renderer reads one file
    # at a time, so it is split here - but both halves keep the span's framing,
    # because a join between takes is not a reason to reframe.
    video: list[VideoClip] = []
    for (start, end), framing in zip(spans, framings):
        pieces = reel.split((start, end)) if reel else [(source, start, end)]
        for piece_src, piece_start, piece_end in pieces:
            if piece_end - piece_start < 1e-3:
                continue
            video.append(VideoClip(src=piece_src, start=piece_start, end=piece_end,
                                   ease=profile.punch.ease, **framing))
    if not video:
        raise ValueError("nothing survived the cut")

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
