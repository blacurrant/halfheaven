"""Burned-in caption geometry, measured rather than guessed.

A live probe against the vision model returned x=0.28 for a dead-centre
caption. Vision models read *style* well (colour name, casing, stroke weight,
word count) and *geometry* badly. So position, size and exact fill are measured
here with OpenCV, and only the semantic attributes are asked of the model.
"""
from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass

import cv2
import numpy as np

# A caption line is wide, and occupies a plausible slice of the frame.
MIN_ASPECT = 1.5
MIN_HEIGHT_PCT = 0.015
MAX_HEIGHT_PCT = 0.25
MIN_WIDTH_PCT = 0.05
MAX_WIDTH_PCT = 1.0  # a caption may span the full frame width


@dataclass(frozen=True)
class CaptionBox:
    x: int
    y: int
    width: int
    height: int
    frame_width: int
    frame_height: int
    fill_hex: str

    @property
    def center_x_pct(self) -> float:
        return (self.x + self.width / 2) / self.frame_width

    @property
    def center_y_pct(self) -> float:
        return (self.y + self.height / 2) / self.frame_height

    @property
    def height_pct(self) -> float:
        return self.height / self.frame_height


def _dominant_fill(region: np.ndarray) -> str:
    """The caption's own colour: the brightest cluster inside its box.

    Burned-in captions are drawn far brighter than their stroke and backdrop,
    so the top of the value distribution is the glyph body.
    """
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    value = hsv[:, :, 2]
    cutoff = np.percentile(value, 85)
    mask = value >= cutoff
    if not mask.any():
        return "#000000"
    b, g, r = (int(np.median(region[:, :, i][mask])) for i in range(3))
    return f"#{r:02X}{g:02X}{b:02X}"


def _group_into_lines(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """Union word boxes that sit on the same text line.

    Words are separated by spaces the morphological close deliberately does not
    bridge - widening that kernel far enough to join them also joins unrelated
    objects. Grouping by vertical overlap joins the line without that cost.
    """
    lines: list[list[tuple[int, int, int, int]]] = []
    for box in sorted(boxes, key=lambda b: b[1]):
        _, y, _, h = box
        for line in lines:
            ly = min(b[1] for b in line)
            lh = max(b[1] + b[3] for b in line) - ly
            overlap = min(y + h, ly + lh) - max(y, ly)
            if overlap > 0.5 * min(h, lh):
                line.append(box)
                break
        else:
            lines.append([box])

    unioned = []
    for line in lines:
        x0 = min(b[0] for b in line)
        y0 = min(b[1] for b in line)
        x1 = max(b[0] + b[2] for b in line)
        y1 = max(b[1] + b[3] for b in line)
        unioned.append((x0, y0, x1 - x0, y1 - y0))
    return unioned


def candidate_boxes(image: np.ndarray) -> list[CaptionBox]:
    """Every text-line-shaped region in a frame, largest first."""
    frame_h, frame_w = image.shape[:2]

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Text has strong local gradient; flat shapes and gradients do not.
    gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    _, binary = cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    # Merge glyphs into words and words into lines.
    kernel_w = max(9, frame_w // 40)
    merged = cv2.morphologyEx(
        binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 3))
    )

    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Individual words first. Anything too tall to be a caption line (a face, a
    # sign, a shape outline) is dropped here rather than confusing the merge.
    words = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if not (MIN_HEIGHT_PCT <= h / frame_h <= MAX_HEIGHT_PCT):
            continue
        if w * h < (frame_w * frame_h) * 1e-4:
            continue
        words.append((x, y, w, h))

    boxes = []
    for x, y, w, h in _group_into_lines(words):
        if h == 0 or w / h < MIN_ASPECT:
            continue
        if not (MIN_WIDTH_PCT <= w / frame_w <= MAX_WIDTH_PCT):
            continue
        boxes.append(
            CaptionBox(
                x=x, y=y, width=w, height=h,
                frame_width=frame_w, frame_height=frame_h,
                fill_hex=_dominant_fill(image[y : y + h, x : x + w]),
            )
        )
    return sorted(boxes, key=lambda b: -b.width * b.height)


def detect_caption_box(path: str | pathlib.Path) -> CaptionBox | None:
    """Largest text-like region in a single frame.

    Adequate for a frame with one text object. On real footage the largest such
    region is often a street sign or an inset, so prefer detect_persistent_caption
    when a video (rather than a frame) is available.
    """
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"could not read image: {path}")
    boxes = candidate_boxes(image)
    return boxes[0] if boxes else None


# A burned-in caption holds a *band*, not a box. Measured on real footage, a
# caption's height swings from 0.02 to 0.21 of frame height as phrases wrap to
# one or two lines, so height is deliberately not part of the match - only the
# band it occupies. Half the shots is enough: a title is often covered by a
# full-frame graphic or an inset in some shots.
PERSISTENCE_FRACTION = 0.5
X_TOLERANCE = 0.06
Y_TOLERANCE = 0.05
MIN_OBSERVATIONS = 3


def _saturation(hex_colour: str) -> float:
    """HSV saturation of a hex colour, 0-1."""
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    high, low = max(r, g, b), min(r, g, b)
    return 0.0 if high == 0 else (high - low) / high


def _same_band(a: CaptionBox, b: CaptionBox) -> bool:
    return (
        abs(a.center_x_pct - b.center_x_pct) <= X_TOLERANCE
        and abs(a.center_y_pct - b.center_y_pct) <= Y_TOLERANCE
    )


def detect_persistent_caption(
    video: str | pathlib.Path, samples_per_shot: int = 2
) -> CaptionBox | None:
    """The burned-in caption of a video, if it has one.

    Distinguishes an overlay from filmed text by the one property that actually
    separates them: an overlay holds its position across cuts, while everything
    behind it changes. Requires the region to recur in most of the video's shots.
    """
    from halfheaven.analyze.shots import detect_shots

    shots = detect_shots(video)
    if len(shots) < 2:
        return None

    capture = cv2.VideoCapture(str(video))
    try:
        observations: list[tuple[int, CaptionBox]] = []
        for shot_index, shot in enumerate(shots):
            for step in range(samples_per_shot):
                fraction = (step + 1) / (samples_per_shot + 1)
                capture.set(cv2.CAP_PROP_POS_MSEC, (shot.start + shot.duration * fraction) * 1000)
                ok, frame = capture.read()
                if not ok:
                    continue
                for box in candidate_boxes(frame):
                    observations.append((shot_index, box))
    finally:
        capture.release()

    clusters: list[list[tuple[int, CaptionBox]]] = []
    for shot_index, box in observations:
        for cluster in clusters:
            if _same_band(cluster[0][1], box):
                cluster.append((shot_index, box))
                break
        else:
            clusters.append([(shot_index, box)])

    required = max(2, math.ceil(PERSISTENCE_FRACTION * len(shots)))
    persistent = [
        c
        for c in clusters
        if len({shot for shot, _ in c}) >= required and len(c) >= MIN_OBSERVATIONS
    ]
    if not persistent:
        return None

    # Widest reach first. Among equally persistent bands, prefer the saturated
    # one: a burned-in caption is drawn in a deliberate brand colour, whereas
    # filmed content that happens to recur (an inset, a wall) is muted.
    def rank(cluster):
        shots_seen = len({shot for shot, _ in cluster})
        saturation = sum(_saturation(box.fill_hex) for _, box in cluster) / len(cluster)
        return (shots_seen, round(saturation, 1), len(cluster))

    best = max(persistent, key=rank)
    boxes = sorted((box for _, box in best), key=lambda b: b.width * b.height)
    return boxes[len(boxes) // 2]
