"""Turning editorial decisions into a validated EditProgram.

The deterministic half of planning. The model contributes word indices and
nothing else; every number below is computed from Whisper's measured timings,
so a timing bug can only live here - not in a prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from halfheaven.analyze.subject import HEADROOM
from halfheaven.schemas import TypePlan
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
    # One entry per span: an (x, y) point, or a bare x for older callers.
    track: list | None = None,
) -> list[dict[str, float | None]]:
    """A framing for each segment, changing only as often as the style implies.

    How long to hold is not a guess: the reference already told us how long it
    holds a shot. Sixteen reframes in a minute reads as nervous, and it was the
    measured pacing - previously unused - that said so.

    Deterministic, so a creator who asks for one change does not get a
    different cut everywhere else.
    """
    def point_of(index: int) -> tuple[float, float] | None:
        if not track or index >= len(track):
            return None
        entry = track[index]
        x, y = (entry, 0.5) if isinstance(entry, (int, float)) else entry
        return float(min(1.0, max(0.0, x))), float(min(1.0, max(0.0, y)))

    def centre_for(index: int, fallback: float) -> float:
        # a tracked position always wins: it is where the subject actually is,
        # and a patterned drift would push a punch-in away from them
        point = point_of(index)
        return point[0] if point else fallback

    def height_for(index: int) -> float:
        point = point_of(index)
        return point[1] if point else 0.5

    if profile.punch.variety <= 0 or len(spans) < 2:
        return [
            {"scale_to": FRAMINGS[-1][0] if i in punched else None,
             "crop_x": centre_for(i, 0.5), "crop_y": height_for(i)}
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
                        "crop_x": centre_for(index, centre), "crop_y": height_for(index)})
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
            "crop_y": height_for(index),
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
    tracker: Callable[[list[Span]], list] | None = None,
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

    # How type is used across the edit, when the reference was measured: how
    # much of the runtime carries it, how often a word turns the accent colour,
    # and where each card sits. Thinning comes first so the accent rate is
    # judged on the cards that survive.
    if profile.type_plan is not None:
        total = sum(clip.end - clip.start for clip in video)
        captions = _thin_captions(captions, profile.type_plan.duty_cycle, total)
        captions = _accent_captions(captions, profile.type_plan.accent_rate)
        captions = _place_captions(captions, profile.type_plan, video, profile.captions.size_pct)

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


# --------------------------------------------------------------------------
# type across the edit: how much, where, and how often it turns colour
# --------------------------------------------------------------------------

# Composed cards sit around the reference's centre of type, offset by its
# measured spread. A fixed pattern rather than a random one: the same edit must
# come out the same twice, and one change must not send every card jumping.
COMPOSED_OFFSETS: tuple[tuple[float, float], ...] = (
    (0.0, 0.0), (-0.9, -0.5), (0.8, -0.25), (-0.45, 0.55), (0.85, 0.45), (-0.8, 0.1),
)
# Half a framed face's height at zoom 1, with room for hair and chin. Measured on
# the pipeline's own output: an unpunched face is about 0.12 of frame height.
FACE_HALF = 0.08
# Where a face sits when nothing located one: the band talking heads occupy.
FACE_BAND_DEFAULT = (0.32, 0.56)
# A caption line's height as a multiple of its size.
TYPE_LINE = 1.25


def _thin_captions(captions: list[Caption], target: float, total: float) -> list[Caption]:
    """Drop cards until type is on screen for the reference's share of the runtime.

    Captioning every word is the clearest tell of auto-subtitles; an edited reel
    leaves much of its runtime clear on purpose. A card carrying a stressed word
    is always kept - it is one the edit chose - and the rest are dropped evenly
    rather than in a block, so no stretch goes bare.
    """
    shown = sum(caption.duration for caption in captions)
    if total <= 0 or not captions or shown / total <= target:
        return captions
    keep = target * total / shown
    kept: list[Caption] = []
    budget = 0.0
    for caption in captions:
        budget += keep
        stressed = any(run.style == EMPHASIS_STYLE for run in caption.runs)
        if stressed or budget >= 1.0:
            kept.append(caption)
            budget -= 1.0
    return kept


def _accent_captions(captions: list[Caption], rate: float) -> list[Caption]:
    """Stress a word on enough cards to match how often the reference turns its
    accent colour. The longest word carries it: short words are the glue
    between the ones that matter."""
    if rate <= 0 or not captions:
        return captions
    plain = [index for index, caption in enumerate(captions)
             if not any(run.style == EMPHASIS_STYLE for run in caption.runs)]
    need = min(round(rate * len(captions)) - (len(captions) - len(plain)), len(plain))
    if need <= 0:
        return captions
    step = len(plain) / need
    chosen = {plain[int(k * step)] for k in range(need)}
    out: list[Caption] = []
    for index, caption in enumerate(captions):
        if index in chosen:
            best = max(range(len(caption.runs)),
                       key=lambda k: len(caption.runs[k].text.strip(".,!?;:'\"")))
            runs = [run.model_copy(update={"style": EMPHASIS_STYLE}) if k == best else run
                    for k, run in enumerate(caption.runs)]
            caption = caption.model_copy(update={"runs": runs})
        out.append(caption)
    return out


def _clip_at(video: list[VideoClip], t: float) -> VideoClip | None:
    """The clip on screen at program time `t`."""
    elapsed = 0.0
    for clip in video:
        length = clip.end - clip.start
        if t < elapsed + length:
            return clip
        elapsed += length
    return video[-1] if video else None


def _face_band(clip: VideoClip | None) -> tuple[float, float]:
    """Where the speaker's face sits in the output frame during a clip.

    The framing already knows: the subject point is the face plus headroom, and
    a punch-in lands it just above centre (measured at y 0.40-0.46). A clip whose
    subject was never located gets the band a talking head occupies.
    """
    if clip is None or clip.crop_y == 0.5:
        return FACE_BAND_DEFAULT
    zoom = clip.scale_to or 1.0
    centre = 0.5 - HEADROOM * zoom if zoom > 1.0 else clip.crop_y - HEADROOM
    half = FACE_HALF * zoom
    return centre - half, centre + half


def _place_captions(captions: list[Caption], plan: TypePlan,
                    video: list[VideoClip], size: float) -> list[Caption]:
    """Place each card the way the reference places its type - and never over a face."""
    out: list[Caption] = []
    for index, caption in enumerate(captions):
        x, y = plan.centroid
        if plan.placement == "composed":
            dx, dy = COMPOSED_OFFSETS[index % len(COMPOSED_OFFSETS)]
            x, y = x + dx * plan.spread, y + dy * plan.spread
        half = size * TYPE_LINE * (1 if len(caption.runs) <= 3 else 2) / 2
        low, high = _face_band(_clip_at(video, caption.t))
        if y + half > low and y - half < high:
            # Type over a face is the one placement that is always wrong. Most
            # cards go above it, where references tend to put type; every third
            # goes below, so a composed edit still moves in both directions.
            above, below = low - half - 0.02, high + half + 0.02
            if index % 3 != 2 and above - half >= 0.08:
                y = above
            elif below + half <= 0.92:
                y = below
            else:
                y = above
        x = min(max(x, 0.2), 0.8)
        y = min(max(y, 0.08 + half), 0.92 - half)
        out.append(caption.model_copy(update={"anchor": (round(x, 4), round(y, 4))}))
    return out
