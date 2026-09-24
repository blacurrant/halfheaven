"""Captions that know where the speaker is.

Two creator-chosen modes, both judged against the subject matte already cut
into the program timeline, so they see exactly the crops and punch-ins the
viewer will:

- "around": a card that would sit on the speaker moves off them - up, down or
  to a side, whichever is nearest - so type never lands on a face.
- "behind": cards carrying a stressed word tuck behind the top of the head.
  That only reads when the text actually passes behind them, and a word the
  head mostly covers is a word nobody can read, so each placement is checked.

Either pass records a moved card's original anchor in `home`, and every pass
starts by putting cards back there - switching modes, or off, never compounds.
"""
from __future__ import annotations

import math
import pathlib
import tempfile

import cv2
import numpy as np
from PIL import Image

from halfheaven.render.caption_frames import CaptionFrame
from halfheaven.render.captions import SIDE_MARGIN_PCT, render_frame
from halfheaven.schemas import Caption, CaptionProfile, EditProgram

EMPHASIS_STYLE = "emphasis"
# --- behind ---
# An effect on every card is no effect; one every few seconds is a rhythm.
MIN_GAP = 6.0
# Share of a card's letters the subject may hide at any moment it is up.
# Beyond this the word is guessed at rather than read.
MAX_COVER = 0.35
# Below this, nobody can tell the card is behind anyone.
MIN_COVER = 0.04
# How far a card moves per try, as a share of frame height, and how many tries.
STEP = 0.02
TRIES = 10
# --- around ---
# A card this little on the speaker is already clear of them: an arm's edge.
CLEAR = 0.02
# Where a card may go. Sides first get a chance at the card's own height.
AROUND_XS = (0.28, 0.72)
AROUND_YS = tuple(round(0.1 + 0.04 * k, 2) for k in range(21))   # 0.10 .. 0.90
# A sideways move is a bigger change to the layout than a vertical one.
SIDEWAYS_COST = 1.5
# --- reading the matte ---
# A row belongs to the subject once this share of it is subject.
ROW_SHARE = 0.015
# How deep below the top of the subject its centre is judged: the head, not the shoulders.
HEAD_DEPTH = 0.08


def _stressed(caption: Caption) -> bool:
    return caption.emphasis or any(run.style == EMPHASIS_STYLE for run in caption.runs)


def _matte_at(track: pathlib.Path, t: float, program: EditProgram) -> np.ndarray | None:
    """The subject at program time `t`, 0..1, placed as the finish pass places it."""
    capture = cv2.VideoCapture(str(track))
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000)
        ok, frame = capture.read()
    finally:
        capture.release()
    if not ok:
        return None
    matte = frame[:, :, 0].astype(np.float32) / 255
    look, canvas = program.look, program.canvas
    if look.is_letterboxed:
        top = int(round(look.letterbox_top_pct * canvas.height))
        bottom = int(round(look.letterbox_bottom_pct * canvas.height))
        content = cv2.resize(matte, (canvas.width, max(2, canvas.height - top - bottom)))
        matte = np.zeros((canvas.height, canvas.width), np.float32)
        matte[top: top + content.shape[0]] = content
    return matte


def _mattes_during(caption: Caption, program: EditProgram, track: pathlib.Path) -> list[np.ndarray]:
    """The subject as the card appears, halfway through, and as it leaves."""
    end = caption.t + caption.duration
    moments = [caption.t + 0.05, (caption.t + end) / 2, max(caption.t, end - 0.05)]
    mattes = [_matte_at(track, t, program) for t in moments]
    return [] if any(m is None for m in mattes) else mattes


def _head(matte: np.ndarray) -> tuple[float, float] | None:
    """The top of the subject and the centre of its head, as frame fractions."""
    height, width = matte.shape
    solid = matte > 0.5
    rows = np.nonzero(solid.sum(axis=1) > ROW_SHARE * width)[0]
    if not len(rows):
        return None
    top = int(rows[0])
    xs = np.nonzero(solid[top: top + int(HEAD_DEPTH * height)])[1]
    return top / height, float(xs.mean()) / width


def _ink(caption: Caption, program: EditProgram, anchor: tuple[float, float],
         scratch: pathlib.Path) -> np.ndarray:
    """Where the card's letters are when it sits at `anchor`, drawn by the renderer itself."""
    profile = program.styles.get(caption.style) or CaptionProfile(present=True)
    path = render_frame(CaptionFrame(runs=caption.runs, duration=0.0), program.canvas, profile,
                        scratch / "card.png", program.styles, anchor=anchor)
    return np.array(Image.open(path))[:, :, 3] > 127


def _cover(ink: np.ndarray, matte: np.ndarray) -> float:
    return float((matte[ink] > 0.5).mean()) if ink.any() else 0.0


# --------------------------------------------------------------------------
# behind
# --------------------------------------------------------------------------


def _tuck(caption: Caption, program: EditProgram, track: pathlib.Path,
          scratch: pathlib.Path) -> Caption | None:
    """The card moved behind the subject's head, or None when it cannot be read there."""
    mattes = _mattes_during(caption, program, track)
    head = _head(mattes[1]) if mattes else None
    if head is None:
        return None
    y, x = head
    for _ in range(TRIES):
        y = min(max(y, 0.08), 0.92)
        ink = _ink(caption, program, (x, y), scratch)
        # Readable for the whole time it is up, visibly behind at its middle.
        worst = max(_cover(ink, matte) for matte in mattes)
        if worst > MAX_COVER:
            y -= STEP
        elif _cover(ink, mattes[1]) < MIN_COVER:
            y += STEP
        else:
            return caption.model_copy(update={"anchor": (round(x, 4), round(y, 4)),
                                              "behind": True, "home": caption.anchor})
    return None


def send_behind(program: EditProgram, subject_track: str | pathlib.Path,
                min_gap: float = MIN_GAP) -> EditProgram:
    """Tuck stressed cards behind the speaker wherever they stay readable."""
    track = pathlib.Path(subject_track)
    last = -math.inf
    out: list[Caption] = []
    with tempfile.TemporaryDirectory() as scratch:
        for caption in sorted(program.captions, key=lambda c: c.t):
            tucked = None
            if _stressed(caption) and caption.t - last >= min_gap:
                tucked = _tuck(caption, program, track, pathlib.Path(scratch))
            if tucked is not None:
                last = caption.t
            out.append(tucked or caption)
    return program.model_copy(update={"captions": out})


# --------------------------------------------------------------------------
# around
# --------------------------------------------------------------------------


class _Stamp:
    """A card's letters, cut to their bounding box, placeable at any anchor.

    Rendering the card once and sliding the stamp is what makes searching
    dozens of positions for dozens of cards affordable. It places the stamp
    with the renderer's own rules - centred on the anchor, kept inside the
    side and top margins - so a position judged clear is clear when drawn.
    """

    def __init__(self, ink: np.ndarray, anchor: tuple[float, float]) -> None:
        self.height, self.width = ink.shape
        ys, xs = np.nonzero(ink)
        self.top, self.left = int(ys.min()), int(xs.min())
        self.mask = ink[self.top: ys.max() + 1, self.left: xs.max() + 1]
        rows, cols = self.mask.shape
        # where the letters sit relative to the anchor the card was drawn at
        self.dy = self.top + rows / 2 - anchor[1] * self.height
        self.dx = self.left + cols / 2 - anchor[0] * self.width

    def cover(self, anchor: tuple[float, float], matte: np.ndarray) -> float:
        rows, cols = self.mask.shape
        side = self.width * SIDE_MARGIN_PCT
        margin = self.height * SIDE_MARGIN_PCT
        centre_x = min(max(anchor[0] * self.width + self.dx, side + cols / 2),
                       self.width - side - cols / 2)
        centre_y = min(max(anchor[1] * self.height + self.dy, margin + rows / 2),
                       self.height - margin - rows / 2)
        left = int(round(centre_x - cols / 2))
        top = int(round(centre_y - rows / 2))
        left = min(max(left, 0), self.width - cols)
        top = min(max(top, 0), self.height - rows)
        under = matte[top: top + rows, left: left + cols] > 0.5
        return float(under[self.mask].mean()) if self.mask.any() else 0.0


def _clear(caption: Caption, program: EditProgram, track: pathlib.Path,
           scratch: pathlib.Path) -> Caption | None:
    """The card moved to the nearest place off the speaker, or None if it already is."""
    mattes = _mattes_during(caption, program, track)
    if not mattes:
        return None
    ink = _ink(caption, program, caption.anchor, scratch)
    if not ink.any():
        return None
    stamp = _Stamp(ink, caption.anchor)
    worst = lambda anchor: max(stamp.cover(anchor, matte) for matte in mattes)
    if worst(caption.anchor) <= CLEAR:
        return None

    x0, y0 = caption.anchor
    candidates = [(x, y) for x in (x0, *AROUND_XS) for y in AROUND_YS]
    distance = lambda a: abs(a[1] - y0) + SIDEWAYS_COST * abs(a[0] - x0)
    scored = [(worst(a), distance(a), a) for a in candidates]
    clear = [s for s in scored if s[0] <= CLEAR]
    # Nearest clear spot; when the speaker fills the frame, the least covered one.
    _, _, best = min(clear, key=lambda s: s[1]) if clear else min(scored)
    return caption.model_copy(update={"anchor": (round(best[0], 4), round(best[1], 4)),
                                      "home": caption.anchor})


def keep_clear(program: EditProgram, subject_track: str | pathlib.Path) -> EditProgram:
    """Move every card that would sit on the speaker to the nearest place that doesn't."""
    track = pathlib.Path(subject_track)
    out: list[Caption] = []
    with tempfile.TemporaryDirectory() as scratch:
        for caption in program.captions:
            out.append(_clear(caption, program, track, pathlib.Path(scratch)) or caption)
    return program.model_copy(update={"captions": out})


# --------------------------------------------------------------------------
# the one entry point
# --------------------------------------------------------------------------


def reset(program: EditProgram) -> EditProgram:
    """Every card back where the planner put it, in front of the picture."""
    return program.model_copy(update={"captions": [
        c.model_copy(update={"anchor": c.home or c.anchor, "behind": False, "home": None})
        for c in program.captions]})


def place_around_subject(program: EditProgram, mode: str,
                         subject_track: str | pathlib.Path | None) -> EditProgram:
    """Apply a caption mode ("off", "around", "behind") from a clean start."""
    program = reset(program)
    if mode == "off" or subject_track is None or not program.captions:
        return program
    if mode == "around":
        return keep_clear(program, subject_track)
    if mode == "behind":
        return send_behind(program, subject_track)
    raise ValueError(f"unknown caption mode {mode!r}")
