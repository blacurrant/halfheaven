"""Turning a reference's zones into a colourist's controls.

The order is a colourist's: correct first (a white balance aimed by the skin),
then the look, per zone (a tone curve, saturation, and the split tone read from
near-neutral pixels), then skin (richer or quieter, never brighter or darker).
Every control is bounded, because a reference can contain anything; the bounds
came from the spike on 2026-09-26, each from a failure it caused:

- an unlimited curve turned h264 blocks on a white wall into patches, so the
  slope is clipped the way CLAHE clips its histogram;
- a reference's lamp is part of the room, not the grade, and stretching a plain
  wall up to it is what made those patches;
- grey-world white balance failed on a cream wall and a blue shirt, so white
  balance is aimed by skin, and capped;
- a subject-wide curve darkened a face along with a bright shirt, so skin keeps
  its own brightness and the room moves instead.

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
SATURATION_RANGE = {"subject": (0.85, 1.15), "background": (0.8, 1.3)}
SKIN_CHROMA_RANGE = (0.85, 1.3)
GRID = np.linspace(0.0, 100.0, 201)
SMOOTH = 13

Zone = Literal["subject", "background", "skin"]


def tone_curve(take_q: list[float], ref_q: list[float], anchor: float,
               fixed: float | None = None) -> list[float]:
    """Output L on GRID: the take's L quantiles mapped onto the reference's, scaled by `anchor`.

    Beyond the range the take showed, the footage keeps its own contrast
    (slope 1) instead of being flattened: a highlight in a frame that was not
    sampled should not be crushed. Then smoothed, slope-limited, and shifted:
    so that `fixed` maps to itself when given (the face, for the subject), or
    else so the take's median lands where the unlimited curve put it.
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
        curve += fixed - np.interp(fixed, GRID, curve)
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


def _zone(zone: str, take: ZoneTone, ref: ZoneTone, anchor: float,
          fixed: float | None = None) -> ZoneControls:
    low, high = SATURATION_RANGE[zone]
    saturation = float(np.clip(ref.median_chroma / max(take.median_chroma, 1e-3), low, high))
    return ZoneControls(curve=tone_curve(take.l_quantiles, ref.l_quantiles, anchor, fixed),
                        saturation=saturation, tint_take=list(take.tints), tint_ref=list(ref.tints))


def plan_grade(take: ZoneLook, ref: ZoneLook, strength: float) -> GradeControls:
    """The controls that move `take` toward `ref`, every one within its bounds."""
    white_balance, turn = _white_balance(take.skin, ref.skin)
    anchor = 1.0
    if take.skin is not None and ref.skin is not None and ref.skin.median_l > 1e-3:
        anchor = float(np.clip(take.skin.median_l / ref.skin.median_l, *ANCHOR_RANGE))
    # The subject's curve pivots on the face, so the face keeps its brightness
    # even where the skin matte is soft or misses it: a bright shirt would
    # otherwise set the subject's level and drag the face down with it.
    face = take.skin.median_l if take.skin is not None else None
    controls = GradeControls(
        strength=strength, white_balance_ab=white_balance, white_balance_deg=turn,
        exposure_anchor=anchor,
        subject=_zone("subject", take.subject, ref.subject, anchor, fixed=face),
        background=_zone("background", take.background, ref.background, anchor),
    )
    if take.skin is None or ref.skin is None:
        return controls
    # Aim the skin's richness at the reference's, from where the subject ops leave it.
    skin = np.array([[[take.skin.median_l, *take.skin.ab]]], np.float32)
    after = apply_controls(skin, controls, "subject")[0, 0]
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
    ab = ab + s * (_tint(graded / controls.exposure_anchor, tone.tint_ref)
                   - _tint(lightness, tone.tint_take))
    out[..., 0] = graded
    out[..., 1:] = ab
    if zone == "skin":
        out[..., 0] = corrected
        out[..., 1:] *= 1.0 + s * (controls.skin_chroma - 1.0)
    out[..., 0] = np.clip(out[..., 0], 0.0, 100.0)
    out[..., 1:] = np.clip(out[..., 1:], -127.0, 127.0)
    return out
