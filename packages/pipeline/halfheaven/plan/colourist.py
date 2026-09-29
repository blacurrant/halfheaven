"""Turning a reference's zones into a colourist's controls.

The order is a colourist's: correct first (a white balance aimed by the skin),
then the look, per zone (a tone curve, saturation, and the split tone read from
the room's near-neutral pixels), then skin (richer or quieter, and exposed
toward the reference's face within bounds, the whole subject moving with it).
Every control is bounded, because a reference can contain anything; the bounds
came from the spike on 2026-09-26, each from a failure it caused:

- an unlimited curve turned h264 blocks on a white wall into patches, so the
  slope is clipped the way CLAHE clips its histogram;
- a reference's lamp is part of the room, not the grade, and stretching a plain
  wall up to it is what made those patches; for the same reason a daylit
  reference may not lift a dim room by more than MAX_LIFT (found on the
  evaluation matrix, where it greyed a room's blacks to L 67);
- grey-world white balance failed on a cream wall and a blue shirt, so white
  balance is aimed by skin, and capped;
- a subject-wide curve darkened a face along with a bright shirt, so the
  subject's curve pivots on the face;
- a face held at its own brightness left the subject looking ungraded against
  a graded room (the day 4 reel's face is 10 L brighter than the take's), so
  the face moves toward the reference's, less far down than up, since darkened
  faces turned muddy;
- pivoting on the face lifted the subject's blacks with it (L 3 -> 11), so a
  lift fades out toward black;
- a reference's near-neutral subject pixels are its clothes: read as a split
  tone, a blue-grey shirt turned the creator's skin pink. The subject takes the
  room's split tone, and skin none; its hue is the white balance's job.

Every op depends only on a pixel's colour and its zone, so each zone bakes into
one 3D LUT (render/lut.py).
"""
from __future__ import annotations

from typing import Literal

import numpy as np

from halfheaven.analyze.zones import BAND_CENTRES
from halfheaven.schemas import GradeControls, SkinTone, ZoneControls, ZoneLook, ZoneTone

WB_MAX_DEG = 12.0
WB_SHARE = 0.8
ANCHOR_RANGE = (0.7, 1.5)
SLOPE_RANGE = (0.12, 1.6)
# How far a tone curve may brighten any tone, in L. Enough for a faded-black
# look; the Day 3 reel's daylit sky lifted a dim room's blacks from 0 to 67.
MAX_LIFT = 12.0
SATURATION_RANGE = {"subject": (0.85, 1.15), "background": (0.8, 1.3)}
SKIN_CHROMA_RANGE = (0.85, 2.0)
FACE_LIFT_RANGE = (-4.0, 8.0)
GRID = np.linspace(0.0, 100.0, 201)
SMOOTH = 13

Zone = Literal["subject", "background", "skin"]


def tone_curve(take_q: list[float], ref_q: list[float], anchor: float,
               fixed: float | None = None, lift: float = 0.0) -> list[float]:
    """Output L on GRID: the take's L quantiles mapped onto the reference's, scaled by `anchor`.

    Beyond the range the take showed, the footage keeps its own contrast
    (slope 1) instead of being flattened: a highlight in a frame that was not
    sampled should not be crushed. Then smoothed, slope-limited, and shifted:
    so that `fixed` maps to `fixed + lift` when given (the face, for the
    subject), or else so the take's median lands where the unlimited curve put
    it. A shift upward fades out below `fixed`, so black stays black.
    """
    take = np.maximum.accumulate(np.asarray(take_q, float) + np.arange(101) * 1e-4)
    ref = np.clip(np.asarray(ref_q, float) * anchor, 0.0, 100.0)
    raw = np.interp(GRID, take, ref)
    raw = np.where(GRID > take[-1], ref[-1] + (GRID - take[-1]), raw)
    raw = np.where(GRID < take[0], ref[0] - (take[0] - GRID), raw)
    pad = SMOOTH // 2
    raw = np.convolve(np.pad(raw, pad, mode="edge"), np.ones(SMOOTH) / SMOOTH, mode="valid")
    step = np.diff(GRID)
    slope = np.clip(np.diff(raw) / step, *SLOPE_RANGE)
    curve = np.concatenate([[raw[0]], raw[0] + np.cumsum(slope * step)])
    if fixed is None:
        median = take[50]
        curve += np.interp(median, GRID, raw) - np.interp(median, GRID, curve)
    else:
        shift = fixed + lift - np.interp(fixed, GRID, curve)
        if shift > 0.0 and fixed > 0.0:
            curve += shift * np.clip(GRID / fixed, 0.0, 1.0)
        else:
            curve += shift
    # Darkening is what grades do; lifting a dim room toward a daylit
    # reference only greys its blacks and raises its noise.
    curve = np.minimum(curve, GRID + MAX_LIFT)
    return [float(v) for v in np.clip(curve, 0.0, 100.0)]


def _hue(ab: tuple[float, float]) -> float:
    return float(np.arctan2(ab[1], ab[0]))


def _white_balance(take: SkinTone | None, ref: SkinTone | None) -> tuple[tuple[float, float], float]:
    """An (a, b) offset turning the take's skin hue part of the way to the reference's."""
    if take is None or ref is None:
        return (0.0, 0.0), 0.0
    gap = (_hue(ref.ab) - _hue(take.ab) + np.pi) % (2 * np.pi) - np.pi
    limit = np.radians(WB_MAX_DEG)
    turn = float(np.clip(gap, -limit, limit) * WB_SHARE)
    chroma = float(np.hypot(*take.ab))
    hue = _hue(take.ab) + turn
    offset = (chroma * np.cos(hue) - take.ab[0], chroma * np.sin(hue) - take.ab[1])
    return (float(offset[0]), float(offset[1])), float(np.degrees(turn))


def _zone(zone: str, take: ZoneTone, ref: ZoneTone, anchor: float, room: tuple[ZoneTone, ZoneTone],
          fixed: float | None = None, lift: float = 0.0) -> ZoneControls:
    low, high = SATURATION_RANGE[zone]
    saturation = float(np.clip(ref.median_chroma / max(take.median_chroma, 1e-3), low, high))
    return ZoneControls(curve=tone_curve(take.l_quantiles, ref.l_quantiles, anchor, fixed, lift),
                        saturation=saturation, tint_take=list(room[0].tints), tint_ref=list(room[1].tints))


def plan_grade(take: ZoneLook, ref: ZoneLook, strength: float) -> GradeControls:
    """The controls that move `take` toward `ref`, every one within its bounds."""
    white_balance, turn = _white_balance(take.skin, ref.skin)
    anchor, lift = 1.0, 0.0
    if take.skin is not None and ref.skin is not None and ref.skin.median_l > 1e-3:
        lift = float(np.clip(ref.skin.median_l - take.skin.median_l, *FACE_LIFT_RANGE))
        anchor = float(np.clip((take.skin.median_l + lift) / ref.skin.median_l, *ANCHOR_RANGE))
    # The subject's curve pivots on the face, so the face lands where the skin
    # does even where the skin matte is soft or misses it: a bright shirt would
    # otherwise set the subject's level and drag the face down with it.
    face = take.skin.median_l if take.skin is not None else None
    room = (take.background, ref.background)
    controls = GradeControls(
        strength=strength, white_balance_ab=white_balance, white_balance_deg=turn,
        exposure_anchor=anchor, face_lift=lift,
        subject=_zone("subject", take.subject, ref.subject, anchor, room, fixed=face, lift=lift),
        background=_zone("background", take.background, ref.background, anchor, room),
    )
    if take.skin is None or ref.skin is None:
        return controls
    # Aim the skin's richness at the reference's, from where the other skin ops leave it.
    skin = np.array([[[take.skin.median_l, *take.skin.ab]]], np.float32)
    after = apply_controls(skin, controls, "skin")[0, 0]
    chroma = float(np.clip(np.hypot(*ref.skin.ab) / max(float(np.hypot(after[1], after[2])), 1e-3),
                           *SKIN_CHROMA_RANGE))
    return controls.model_copy(update={"skin_chroma": chroma})


def _tint(lightness: np.ndarray, table: list[tuple[float, float]]) -> np.ndarray:
    table = np.asarray(table, np.float32)
    return np.stack([np.interp(lightness, BAND_CENTRES, table[:, 0]),
                     np.interp(lightness, BAND_CENTRES, table[:, 1])], axis=-1)


def apply_controls(lab: np.ndarray, controls: GradeControls, zone: Zone) -> np.ndarray:
    """One zone's grade on LAB pixels shaped (..., 3). Strength 0 returns them unchanged."""
    s = controls.strength
    out = np.array(lab, dtype=np.float32, copy=True)
    out[..., 1] += s * controls.white_balance_ab[0]
    out[..., 2] += s * controls.white_balance_ab[1]
    corrected = out[..., 0].copy()
    tone = controls.background if zone == "background" else controls.subject
    lightness = out[..., 0]
    graded = lightness + s * (np.interp(lightness, GRID, tone.curve) - lightness)
    ab = out[..., 1:] * (1.0 + s * (tone.saturation - 1.0))
    if zone != "skin":
        ab = ab + s * (_tint(graded / controls.exposure_anchor, tone.tint_ref)
                       - _tint(lightness, tone.tint_take))
    out[..., 0] = graded
    out[..., 1:] = ab
    if zone == "skin":
        out[..., 0] = corrected + s * controls.face_lift
        out[..., 1:] *= 1.0 + s * (controls.skin_chroma - 1.0)
    out[..., 0] = np.clip(out[..., 0], 0.0, 100.0)
    out[..., 1:] = np.clip(out[..., 1:], -127.0, 127.0)
    return out
