"""Turning a caption card into the still frames that render it.

A card becomes several frames: one per word for an appending or karaoke
reveal, plus a few short frames while a word pops in. The caption track is
already a concat of stills with durations, so animation costs nothing
structurally - it is simply more entries in the same list.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from halfheaven.schemas import Caption, CaptionProfile, TextRun

# A pop is sampled at this many steps; more is smoother and more files.
POP_STEPS = 3


@dataclass(frozen=True)
class CaptionFrame:
    runs: list[TextRun]
    duration: float
    visible: int | None = None   # words shown; None means all of them
    active: int | None = None    # the word being spoken
    entering: int | None = None  # the word currently animating in
    progress: float = 1.0        # 0..1 through that animation

    @property
    def shown(self) -> list[TextRun]:
        return self.runs if self.visible is None else self.runs[: self.visible]


def frames_for(caption: Caption, profile: CaptionProfile, program_end: float) -> list[CaptionFrame]:
    """Expand one card into the frames that draw it, in order."""
    runs = caption.runs
    start, end = caption.t, min(program_end, caption.t + caption.duration)
    if end <= start or not runs:
        return []

    timed = [r.t for r in runs if r.t is not None]
    if profile.reveal == "instant" or len(timed) < len(runs) or len(runs) == 1:
        return [CaptionFrame(runs=runs, duration=end - start, active=None)]

    moments = [max(start, t) for t in timed]
    frames: list[CaptionFrame] = []
    pop = profile.enter != "none" and profile.enter_ms > 0

    for index, at in enumerate(moments):
        until = min(end, moments[index + 1] if index + 1 < len(moments) else end)
        if until <= at:
            continue
        # karaoke keeps the whole card up and marks the spoken word; append
        # builds the card a word at a time
        visible = None if profile.reveal == "karaoke" else index + 1
        active = index if profile.active != "none" else None
        span = until - at

        pop_total = min(profile.enter_ms / 1000.0, span * 0.6) if pop else 0.0
        if pop_total > 0:
            step = pop_total / POP_STEPS
            for k in range(POP_STEPS):
                frames.append(CaptionFrame(runs=runs, duration=step, visible=visible,
                                           active=active, entering=index,
                                           progress=(k + 1) / POP_STEPS))
        rest = span - pop_total
        if rest > 1e-4:
            frames.append(CaptionFrame(runs=runs, duration=rest, visible=visible, active=active))

    return frames
