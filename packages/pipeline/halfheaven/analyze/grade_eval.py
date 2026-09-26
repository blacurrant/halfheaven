"""Does the colourist grade beat today's, and does it hold together at the edge?

Runs the grade alone - no transcription, no editing - on whole takes. Each take
is rendered once with today's single LUT and once with the colourist grade,
through the real renderer, and both are measured against the reference.

    python -m halfheaven.analyze.grade_eval --takes a.mp4 b.mp4 \\
        --references r1.mp4 r2.mp4 --out work/grade_eval [--strength 0.85]
"""
from __future__ import annotations

import cv2
import numpy as np

SEAM_LIMIT = 2.0        # L: a rim or line the grade may add at the matte edge
FLICKER_LIMIT = 1.0     # L per frame the grade may add over the room or the face
FACE_LIMIT = 2.0        # L the face may move from the raw footage
# Rings round the matte's 0.5 contour, as shares of frame height.
EDGE_RING = 0.0035
NEAR_RING = (0.005, 0.014)
MIN_RING_PIXELS = 50


def _signed_distance(alpha: np.ndarray) -> np.ndarray:
    """Pixels from the matte's 0.5 contour: positive inside the subject, negative outside."""
    inside = (alpha > 0.5).astype(np.uint8)
    depth = cv2.distanceTransform(inside, cv2.DIST_L2, 3)
    reach = cv2.distanceTransform(1 - inside, cv2.DIST_L2, 3)
    return np.where(inside > 0, depth, -reach)


def seam(lightness: np.ndarray, alpha: np.ndarray) -> float | None:
    """How much brighter (+) or darker (-) the matte's edge is than both sides of it, in L.

    A rim or an outline is exactly an extreme at the edge. Compare an output's
    seam with the raw footage's: hair has its own dark edge before any grade.
    """
    distance = _signed_distance(alpha) / alpha.shape[0]
    edge = np.abs(distance) <= EDGE_RING
    inner = (distance >= NEAR_RING[0]) & (distance <= NEAR_RING[1])
    outer = (distance <= -NEAR_RING[0]) & (distance >= -NEAR_RING[1])
    if min(edge.sum(), inner.sum(), outer.sum()) < MIN_RING_PIXELS:
        return None
    return float(lightness[edge].mean() - (lightness[inner].mean() + lightness[outer].mean()) / 2)


def flicker(frames: list[np.ndarray], raw_frames: list[np.ndarray], alphas: list[np.ndarray],
            skins: list[np.ndarray]) -> dict[str, float | None]:
    """Frame-to-frame change in L the grade adds over the footage's own, for the room and the face."""
    room, face = [], []
    for k in range(1, len(frames)):
        raw_change = np.abs(raw_frames[k] - raw_frames[k - 1])
        still = (alphas[k] < 0.1) & (alphas[k - 1] < 0.1) & (raw_change < 1.0)
        if still.sum() >= 500:
            room.append(float(np.abs(frames[k] - frames[k - 1])[still].mean() - raw_change[still].mean()))
        now, before = skins[k] > 0.6, skins[k - 1] > 0.6
        if now.sum() >= 200 and before.sum() >= 200:
            graded = abs(np.median(frames[k][now]) - np.median(frames[k - 1][before]))
            shot = abs(np.median(raw_frames[k][now]) - np.median(raw_frames[k - 1][before]))
            face.append(float(graded - shot))
    return {"room": float(np.mean(room)) if room else None,
            "face": float(np.mean(face)) if face else None}
