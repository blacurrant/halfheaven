"""Measuring a video's colour statistics for transfer.

Sampled from the content band only: black bars are not picture, and averaging
them in would darken every grade derived from the reference.
"""
from __future__ import annotations

import pathlib

import cv2
import numpy as np

from halfheaven.analyze.framing import Framing, detect_letterbox
from halfheaven.render.lut import ColorStats

SAMPLES = 16


def measure_color_stats(
    video: str | pathlib.Path,
    framing: Framing | None = None,
    samples: int = SAMPLES,
) -> ColorStats:
    if framing is None:
        framing = detect_letterbox(video)

    capture = cv2.VideoCapture(str(video))
    try:
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        collected: list[np.ndarray] = []
        for index in range(samples):
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(total * (index + 0.5) / samples))
            ok, frame = capture.read()
            if not ok:
                continue
            top, bottom = framing.content_rows(frame.shape[0])
            band = frame[top:bottom]
            if band.size == 0:
                continue
            rgb = cv2.cvtColor(band, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            collected.append(cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).reshape(-1, 3))
    finally:
        capture.release()

    if not collected:
        return ColorStats(mean=(50.0, 0.0, 0.0), std=(1.0, 1.0, 1.0))

    pixels = np.concatenate(collected, axis=0)
    mean = pixels.mean(axis=0)
    std = pixels.std(axis=0)
    return ColorStats(
        mean=(float(mean[0]), float(mean[1]), float(mean[2])),
        std=(float(std[0]), float(std[1]), float(std[2])),
    )
