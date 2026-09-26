"""Reading a picture as zones: the subject, the room behind them, and skin.

A grade is read per zone because one set of numbers for the whole frame is
mostly the room (62% of noedit's pixels), and a colourist moves the room and
the face differently. The same reader serves the reference and the creator's
takes; only where the masks come from differs. The reference's come from
MediaPipe's parts, the takes' from their own mattes.
"""
from __future__ import annotations

import pathlib
from typing import Callable, Iterable, Iterator

import cv2
import numpy as np

from halfheaven.analyze.matte import BACKGROUND, BODY_SKIN, FACE_SKIN
from halfheaven.schemas import SkinTone, TakeMatte, ZoneLook, ZoneTone

# L band edges for the near-neutral tint table, i.e. the split tone.
BANDS = (0.0, 12.0, 25.0, 40.0, 55.0, 70.0, 101.0)
BAND_CENTRES = tuple((lo + hi) / 2 for lo, hi in zip(BANDS[:-1], BANDS[1:]))
NEUTRAL_CHROMA = 15.0
SHADOW_L = 20.0
MIN_BAND_PIXELS = 300
MIN_NEUTRAL_PIXELS = 200
MIN_ZONE_PIXELS = 2000
MIN_SKIN_PIXELS = 500
# Colour statistics survive downscaling; text does not, but none is read here.
MAX_SIDE = 640
# Reference masks: the person eroded and the room outside the person dilated,
# both by this share of height, so the edge band counts in neither zone.
EDGE_MARGIN = 0.005
MIN_PERSON_SHARE = 0.05
MIN_PERSON_FRAMES = 10
# Take mattes are soft; only their confident parts are read.
SUBJECT_ALPHA = 0.9
BACKGROUND_ALPHA = 0.1
SKIN_WEIGHT = 0.6
TAKE_FRAMES = 16
TAKE_FRAMES_CAP = 48

# (lab, subject, background, skin): HxWx3 float32 LAB and three HxW bool masks.
ZoneSample = tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
# MediaPipe's multiclass segmenter: RGB uint8 and a timestamp in, class per pixel out.
PartsFn = Callable[[np.ndarray, int], np.ndarray]


def to_lab(bgr: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)


def shrink(bgr: np.ndarray, max_side: int = MAX_SIDE) -> np.ndarray:
    height, width = bgr.shape[:2]
    scale = max_side / max(height, width)
    if scale >= 1.0:
        return bgr
    size = (max(2, round(width * scale)), max(2, round(height * scale)))
    return cv2.resize(bgr, size, interpolation=cv2.INTER_AREA)


def _tone(pixels: np.ndarray) -> ZoneTone:
    lightness = pixels[:, 0]
    chroma = np.hypot(pixels[:, 1], pixels[:, 2])
    neutral = chroma < NEUTRAL_CHROMA
    overall = ((float(pixels[neutral, 1].mean()), float(pixels[neutral, 2].mean()))
               if neutral.sum() >= MIN_NEUTRAL_PIXELS else (0.0, 0.0))
    tints = []
    for lo, hi in zip(BANDS[:-1], BANDS[1:]):
        band = neutral & (lightness >= lo) & (lightness < hi)
        tints.append((float(pixels[band, 1].mean()), float(pixels[band, 2].mean()))
                     if band.sum() >= MIN_BAND_PIXELS else overall)
    shadows = neutral & (lightness < SHADOW_L)
    return ZoneTone(
        l_quantiles=[float(v) for v in np.percentile(lightness, np.arange(101))],
        mean_l=float(lightness.mean()),
        median_chroma=float(np.median(chroma)),
        tints=tints,
        shadow_tint_a=float(pixels[shadows, 1].mean()) if shadows.sum() >= MIN_NEUTRAL_PIXELS else None,
    )


def read_zone_look(samples: Iterable[ZoneSample]) -> ZoneLook | None:
    """Pool every sample's zones; None when the subject or the room is too small to read."""
    subject, background, skin = [], [], []
    for lab, is_subject, is_background, is_skin in samples:
        subject.append(lab[is_subject])
        background.append(lab[is_background])
        skin.append(lab[is_skin])
    if not subject:
        return None
    subject_px = np.concatenate(subject)
    background_px = np.concatenate(background)
    skin_px = np.concatenate(skin)
    if len(subject_px) < MIN_ZONE_PIXELS or len(background_px) < MIN_ZONE_PIXELS:
        return None
    skin_tone = None
    if len(skin_px) >= MIN_SKIN_PIXELS:
        skin_tone = SkinTone(ab=(float(skin_px[:, 1].mean()), float(skin_px[:, 2].mean())),
                             mean_l=float(skin_px[:, 0].mean()),
                             median_l=float(np.median(skin_px[:, 0])))
    return ZoneLook(subject=_tone(subject_px), background=_tone(background_px), skin=skin_tone)


def summarise(look: ZoneLook | None) -> dict[str, float | None]:
    """The five numbers the scorecard compares between an output and its reference."""
    summary: dict[str, float | None] = dict.fromkeys(
        ("face_above_background", "background_l", "skin_chroma", "skin_hue", "shadow_tint"))
    if look is None:
        return summary
    summary["background_l"] = round(look.background.l_quantiles[50], 2)
    if look.background.shadow_tint_a is not None:
        summary["shadow_tint"] = round(look.background.shadow_tint_a, 2)
    skin = look.skin
    if skin is not None:
        summary["face_above_background"] = round(skin.mean_l - look.background.mean_l, 2)
        summary["skin_chroma"] = round(float(np.hypot(*skin.ab)), 2)
        summary["skin_hue"] = round(float(np.degrees(np.arctan2(skin.ab[1], skin.ab[0]))), 2)
    return summary


def _frame(capture: cv2.VideoCapture, index: int) -> np.ndarray | None:
    capture.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = capture.read()
    return frame if ok else None


def _weight(frame: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """A grayscale matte frame as 0..1 at `size` (width, height)."""
    return cv2.resize(frame[..., 0], size, interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def _take_samples(take: str, matte: TakeMatte, count: int) -> Iterator[ZoneSample]:
    footage = cv2.VideoCapture(str(take))
    subject = cv2.VideoCapture(matte.subject)
    skin = cv2.VideoCapture(matte.skin) if matte.skin else None
    try:
        total = int(footage.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        for i in range(count):
            index = int(total * (i + 0.5) / count)
            frame, alpha = _frame(footage, index), _frame(subject, index)
            if frame is None or alpha is None:
                continue
            small = shrink(frame)
            size = (small.shape[1], small.shape[0])
            # Mattes are written at <= 1280 on the long side, so a 4K take's
            # matte is smaller than the take: both are brought to one size.
            weight = _weight(alpha, size)
            skin_frame = _frame(skin, index) if skin is not None else None
            skin_weight = _weight(skin_frame, size) if skin_frame is not None else np.zeros_like(weight)
            yield to_lab(small), weight > SUBJECT_ALPHA, weight < BACKGROUND_ALPHA, skin_weight > SKIN_WEIGHT
    finally:
        footage.release()
        subject.release()
        if skin is not None:
            skin.release()


def take_zone_look(takes: list[str], mattes: dict[str, TakeMatte]) -> ZoneLook | None:
    """The creator's takes, pooled: 16 frames each, 48 at most. None if any take has no matte."""
    if not takes or any(take not in mattes for take in takes):
        return None
    per_take = max(1, min(TAKE_FRAMES, TAKE_FRAMES_CAP // len(takes)))
    return read_zone_look(sample for take in takes
                          for sample in _take_samples(take, mattes[take], per_take))


def reference_zone_look(path: str | pathlib.Path, times: list[float],
                        parts: PartsFn | None = None) -> ZoneLook | None:
    """The reference at `times` (seconds). None unless a person fills >= 5% of >= 10 frames."""
    owned = None
    if parts is None:
        from halfheaven.analyze.matte import MediaPipeParts

        owned = MediaPipeParts()
        parts = owned.parts
    capture = cv2.VideoCapture(str(path))
    samples: list[ZoneSample] = []
    last_ms = -1
    try:
        for t in times:
            ms = int(round(t * 1000))
            if ms <= last_ms:       # the segmenter's clock must only move forward
                continue
            last_ms = ms
            capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, frame = capture.read()
            if not ok:
                continue
            small = shrink(frame)
            height, width = small.shape[:2]
            classes = cv2.resize(parts(cv2.cvtColor(small, cv2.COLOR_BGR2RGB), ms), (width, height),
                                 interpolation=cv2.INTER_NEAREST)
            person = classes != BACKGROUND
            if person.mean() < MIN_PERSON_SHARE:
                continue
            radius = max(1, round(EDGE_MARGIN * height))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
            person8 = person.astype(np.uint8)
            subject = cv2.erode(person8, kernel).astype(bool)
            background = ~cv2.dilate(person8, kernel).astype(bool)
            skin = subject & ((classes == FACE_SKIN) | (classes == BODY_SKIN))
            samples.append((to_lab(small), subject, background, skin))
    finally:
        capture.release()
        if owned is not None:
            owned.close()
    if len(samples) < MIN_PERSON_FRAMES:
        return None
    return read_zone_look(samples)
