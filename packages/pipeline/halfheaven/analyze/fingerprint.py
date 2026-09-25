"""What a reference video can tell us about how it was edited.

This is the measurement half of the product: a creator points at a reel they
like, and we recover the decisions behind it. The split that matters is between
what is *nameable* and what is not. "Remove the silences", "make it warmer" - a
creator can say those, so they belong in a control, not in a detector. How the
text behaves, how the rhythm sits against the music, how much of the runtime is
not footage at all - nobody can put those into words, and those are what this
module exists to recover.

So we deliberately measure *structure and proportion* rather than pixels. An
exact typeface or a specific caption position is both hard to recover and not
worth recovering: it belongs to the reference's brand, not its style. A cut
cadence, a text duty cycle, a placement spread transfer to anyone's footage.
The rule of thumb throughout: measure the thing that would still be true if the
reference had been shot by someone else.

Every field carries a `Confidence`. A short reference, or one whose text is
always occluded, should yield *fewer* measurements rather than worse ones -
silently returning a default that looks like a measurement is how a pipeline
ends up confidently applying something it never saw.
"""
from __future__ import annotations

import contextlib
import dataclasses
import enum
import functools
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from halfheaven.analyze.framing import detect_letterbox
from halfheaven.analyze.shots import Shot, detect_shots, pacing
from halfheaven.media.probe import probe

# Motion and colour are measured at this width; text is not. Downscaling
# averages a glyph's stroke into whatever is behind it, which pushes it out of
# the brightness range that identifies it - a caption simply disappears before
# it can be masked. So text is masked at native resolution and everything else
# gets the cheap frame.
ANALYSIS_WIDTH = 240

# A graphic is a frame built from a few flat colours: a full-bleed card, a
# paper product plate. The test is how much of the frame the single commonest
# colour occupies. Frame variance cannot do this job - a clear sky is flat and
# is still photography, and grading a reference is meant to learn from its
# photography, not from its title cards.
GRAPHIC_MODAL_SHARE = 0.45

# ...and carries almost no photographic texture. Modal share alone cannot tell
# a full-bleed card from a layout that mattes a picture into a flat panel -
# both are dominated by one colour. One reference reads as 45% "cards" on that
# test when it is really footage in a designed frame, so the second half of the
# question is whether anything in the frame still looks photographed.
GRAPHIC_MAX_TEXTURE = 0.30

# A glyph occupies this much of the frame's height. Below the floor it is
# grain; above the ceiling it is a subject, not a letter.
GLYPH_MIN_HEIGHT = 0.012
GLYPH_MAX_HEIGHT = 0.22

# How many similarly-sized shapes must share a baseline before we call it a
# line of type. Three is enough to exclude texture and cheap enough to find.
MIN_GLYPHS_PER_ROW = 3

# The widest gap allowed between neighbouring letters, as a multiple of their
# height. Word spaces and loose tracking fit inside it; unrelated marks that
# happen to share a baseline do not.
LETTER_GAP = 1.6

# A caption's treatment can only be judged against a ground bright enough to
# show a shadow. On Day 3's maroon cards a dark shadow is invisible, and those
# frames outvoted the sky ones 43 to 33 - reading a soft drop shadow as "none".
HALO_MIN_GROUND = 90

# Below this share of the frame, what we found is noise - a highlight on a
# railing, not a caption.
TEXT_AREA_FLOOR = 0.0015


class Confidence(enum.Enum):
    """How much of a measurement to believe.

    MEASURED is a real reading. INFERRED is derived from one, and inherits its
    doubt. ABSENT means we looked and found nothing - which is a finding, and
    must never be confused with a default.
    """

    MEASURED = "measured"
    INFERRED = "inferred"
    ABSENT = "absent"


@dataclass(frozen=True)
class Reading:
    """A value, how sure we are, and the evidence behind it."""

    value: Any
    confidence: Confidence = Confidence.MEASURED
    note: str = ""

    def __bool__(self) -> bool:
        return self.confidence is not Confidence.ABSENT

    @staticmethod
    def absent(note: str) -> "Reading":
        return Reading(value=None, confidence=Confidence.ABSENT, note=note)


# --------------------------------------------------------------------------
# one decode pass
# --------------------------------------------------------------------------


@dataclass
class FrameStats:
    """Everything we need from one frame, so the file is decoded once."""

    t: float
    mean_rgb: tuple[float, float, float]
    modal_share: float                     # how much of the frame is one colour
    graphic: bool
    text_area: float                       # share of frame that is glyph
    text_centroid: tuple[float, float] | None
    text_bbox: tuple[float, float, float, float] | None
    accent_share: float                    # share of glyph pixels that are the accent
    glyph_height: float                    # median component height, frame-relative
    stroke_width: float                    # median glyph stroke, frame-relative
    stroke_modulation: float               # within-frame stroke variation
    slant: float                           # glyph lean; >0 leans right, italic
    motion: float
    zoom: float
    halo: tuple[float, float] | None = None   # ring darkness, and its lean down-right


def _text_masks(bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Candidate glyph pixels: bright ones, and saturated accent ones.

    Two masks rather than one because the accent word is the single most
    characterful thing a caption does, and folding it into a general "text"
    mask throws away the fact that it was a different colour.
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    sat, val = hsv[:, :, 1], hsv[:, :, 2]
    bright = ((val > 218) & (sat < 60)).astype(np.uint8)
    # Any strongly saturated, reasonably bright pixel is a candidate accent -
    # not just red. The hue is recovered later from the pixels themselves, so
    # a creator whose accent is cyan is measured as faithfully as this one.
    accent = ((sat > 140) & (val > 110)).astype(np.uint8)
    return bright, accent


def _glyphs(bright: np.ndarray, accent: np.ndarray
            ) -> tuple[np.ndarray, list[float], np.ndarray, set[int]]:
    """Reduce candidate pixels to those that behave like set type.

    Brightness alone is hopeless: a white balaclava, a blown-out sky and a
    sheet of cream paper are all bright. What separates type from all of them
    is that letters sit in rows - several similarly-sized shapes sharing a
    baseline. That single constraint is what makes this reliable, and it is
    why the mask is built from components rather than from morphology.

    Returns the glyph mask, the heights of the components that survived, and
    the label image plus surviving labels so slant can be measured per letter
    without segmenting twice.
    """
    height, width = bright.shape
    raw = cv2.bitwise_or(bright, accent)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(raw, connectivity=8)

    candidates: list[tuple[int, float, float]] = []
    for index in range(1, count):
        box_w = stats[index, cv2.CC_STAT_WIDTH]
        box_h = stats[index, cv2.CC_STAT_HEIGHT]
        area = stats[index, cv2.CC_STAT_AREA]
        # Too small to be a letter, too tall to be one, or wide enough to be
        # scenery rather than a word.
        if not (GLYPH_MIN_HEIGHT * height <= box_h <= GLYPH_MAX_HEIGHT * height):
            continue
        if box_w > 0.5 * width or area < 40:
            continue
        # A letter is neither a solid blob nor a hairline: its ink fills part
        # of its box. This drops both filled shapes and thin scratches.
        fill = area / max(box_w * box_h, 1)
        if not (0.12 <= fill <= 0.92):
            continue
        candidates.append((index, stats[index, cv2.CC_STAT_TOP] + box_h, box_h,
                           stats[index, cv2.CC_STAT_LEFT], box_w))

    mask = np.zeros_like(raw)
    kept: set[int] = set()
    heights: list[float] = []
    for _, baseline, box_h, _, _ in candidates:
        row = sorted(
            (left, other, other_h, other_w)
            for other, other_baseline, other_h, left, other_w in candidates
            if abs(other_baseline - baseline) <= 0.35 * box_h
            and 0.45 <= other_h / max(box_h, 1) <= 2.2
        )
        if len(row) < MIN_GLYPHS_PER_ROW:
            continue
        # Sharing a baseline is not quite enough: scattered marks of a uniform
        # size - a knit texture, a row of highlights - will line up by chance.
        # Letters in a word are also *adjacent*, so keep only the longest run
        # with no wide gap in it. Chance alignments do not survive that.
        runs: list[list[tuple[int, int, int, int]]] = []
        run = [row[0]]
        for entry in row[1:]:
            previous = run[-1]
            gap = entry[0] - (previous[0] + previous[3])
            if gap <= LETTER_GAP * max(entry[2], previous[2]):
                run.append(entry)
            else:
                runs.append(run)
                run = [entry]
        runs.append(run)
        # Every run long enough to be a word counts, not just the longest one.
        # A word passing behind someone arrives here as two runs with a
        # silhouette-shaped hole between them; keeping only the bigger half
        # would throw away the very evidence the depth test looks for.
        keepers = [entry for group in runs if len(group) >= MIN_GLYPHS_PER_ROW
                   for entry in group]
        if not keepers:
            continue
        for _, other, other_h, _ in keepers:
            if other not in kept:
                kept.add(other)
                heights.append(float(other_h))
                mask[labels == other] = 1
    return mask, heights, labels, kept


def _modal_share(small: np.ndarray) -> float:
    """How much of the frame the single commonest colour occupies.

    Colours are quantised before counting, so a card with a slight vignette
    still reads as one colour rather than a thousand near-identical ones.

    The caller is expected to have cropped away any letterbox first. A reel
    that mattes its image into the top half and captions the black below is
    still photography, and counting those bars made one such reference measure
    as 45% designed cards - a wrong answer this test cannot see on its own.
    """
    quantised = (small // 24).reshape(-1, 3)
    _, counts = np.unique(quantised, axis=0, return_counts=True)
    return float(counts.max()) / len(quantised)


def _textured_share(small: np.ndarray, ignore: np.ndarray | None = None) -> float:
    """How much of the frame carries photographic detail.

    Local standard deviation: grain, fabric and foliage vary from pixel to
    pixel; ink on a flat plate does not. Line art sits between the two, which
    is why the threshold is generous rather than tight.

    `ignore` masks out set type. Every letter is a hard edge, so a caption laid
    over a flat card makes that card measure as textured, the card stops
    counting as a graphic, and its colour lands back in the grade - which is
    the exact bug this whole test exists to prevent.
    """
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
    mean = cv2.boxFilter(gray, -1, (9, 9))
    mean_square = cv2.boxFilter(gray * gray, -1, (9, 9))
    textured = np.sqrt(np.maximum(mean_square - mean * mean, 0)) > 7
    if ignore is not None:
        keep = ~ignore.astype(bool)
        if keep.sum() < 0.15 * keep.size:
            return 0.0      # almost nothing but type; judge it by colour alone
        return float(textured[keep].mean())
    return float(textured.mean())


def _slant(mask: np.ndarray, labels: np.ndarray, kept: set[int]) -> float:
    """How far the letters lean, as a shear ratio.

    Second-order image moments give it directly: mu11 over mu02 is the
    horizontal shift per unit of height, which is what italic *is*. Measured
    per letter and then taken as a median, so one leaning shape in a row of
    upright ones cannot tilt the answer.

    This is the only thing that distinguishes an editorial italic from its
    roman, and without it a reference set in italic comes back upright.
    """
    shears: list[float] = []
    for label in kept:
        ys, xs = np.nonzero(labels == label)
        if ys.size < 40:
            continue
        y = ys.astype(np.float64)
        x = xs.astype(np.float64)
        mu02 = ((y - y.mean()) ** 2).mean()
        if mu02 < 1.0:
            continue
        shears.append(float(((x - x.mean()) * (y - y.mean())).mean() / mu02))
    if len(shears) < 3:
        return 0.0
    # Rows read top-down, so a right-leaning letter has ink drifting left as y
    # grows: the raw covariance is negative for italic. Flip it so that
    # "positive means italic" reads the way anyone would expect.
    return -float(np.median(shears))


def _stroke_stats(mask: np.ndarray, labels: np.ndarray, kept: set[int]) -> tuple[float, float]:
    """Median stroke thickness in pixels, and how much it swells within a letter.

    The distance transform's ridge through a stroke is half its thickness, so
    doubling the median ridge gives the pen width. Modulation - thick stems
    against hairline joins - is what separates a didone from a grotesque
    without having to identify either.

    Both must be measured *inside a single letter*. Pooled over a whole frame
    the spread reports the difference between a big word and a small one, which
    is a layout fact rather than a property of the typeface: measured that way
    a flat geometric sans scored 0.51 and resolved to a serif.
    """
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    # Only the medial axis carries stroke width. Every other pixel of a glyph
    # is part way to an edge, and pooling those swamps the difference between
    # faces: measured over whole glyphs, a grotesque and a didone both scored
    # about 0.57 and the reading was useless.
    peak = cv2.dilate(dist, np.ones((3, 3), np.float32))
    spine = (dist > 1.0) & (dist >= peak - 1e-6)

    widths: list[float] = []
    ratios: list[float] = []
    for label in kept:
        ridge = dist[spine & (labels == label)]
        if ridge.size < 8:
            continue
        widths.append(float(np.median(ridge) * 2))
        thin = float(np.percentile(ridge, 10))
        ratios.append(float(np.percentile(ridge, 90) / max(thin, 1e-6)))
    if not widths:
        return 0.0, 0.0
    # A stem-to-hairline ratio of 1 is a grotesque and 6 is a didone, so the
    # useful range is 1..6; normalise it to 0..1 for matching.
    return float(np.median(widths)), float(min(max((np.median(ratios) - 1.0) / 5.0, 0.0), 1.0))


def _halo(frame: np.ndarray, glyph: np.ndarray) -> tuple[float, float] | None:
    """How the pixels hugging each letter differ from the background just beyond.

    An outline darkens a thin ring all the way round; a drop shadow darkens it on
    one side, below and right; bare type does neither. Returns the ring's darkness
    relative to the background, and how much of that darkening leans down-right.
    It matters because a heavy black outline is the single loudest thing that
    makes type read as subtitles, and it was being applied by default.
    """
    if glyph.sum() < 200:
        return None
    lum = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    ink = glyph.astype(bool)
    near = cv2.dilate(glyph, np.ones((5, 5), np.uint8)).astype(bool) & ~ink
    far = (cv2.dilate(glyph, np.ones((17, 17), np.uint8)).astype(bool)
           & ~cv2.dilate(glyph, np.ones((9, 9), np.uint8)).astype(bool))
    below = near & np.roll(np.roll(ink, 3, 0), 3, 1)
    above = near & np.roll(np.roll(ink, -3, 0), -3, 1)
    if not (near.any() and far.any() and below.any() and above.any()):
        return None
    background = float(lum[far].mean())
    # The ground is judged well clear of the letters - 10 to 15 px out, beyond
    # any outline. A closer ring sits inside a heavy stroke, reads it as a dark
    # background, and abstains on exactly the treatment it should catch.
    ground = (cv2.dilate(glyph, np.ones((31, 31), np.uint8)).astype(bool)
              & ~cv2.dilate(glyph, np.ones((21, 21), np.uint8)).astype(bool))
    if background < 1 or not ground.any() or float(lum[ground].mean()) < HALO_MIN_GROUND:
        return None     # a shadow cannot be seen against a darker ground: abstain
    return ((background - float(lum[near].mean())) / background,
            (float(lum[above].mean()) - float(lum[below].mean())) / background)


def _decor_kind(darkness: float, lean: float) -> str:
    """Name the treatment a halo implies. Thresholds sit in the gaps between the
    renderer's own outline, soft and hard shadows, and bare type, measured over
    a textured background."""
    if darkness > 0.35 and lean < 0.2:
        return "stroke"
    if lean > 0.5:
        return "shadow_hard"
    if lean > 0.12 or darkness > 0.05:
        return "shadow_soft"
    return "none"


def _scan(path: pathlib.Path, stride: int = 1) -> tuple[list[FrameStats], list[np.ndarray], float]:
    """Decode once, collecting per-frame statistics and accent pixel samples.

    `stride` samples every nth frame. Masking type at native resolution is the
    expensive step and nothing measured here changes within a few hundredths of
    a second: a caption card lasts over a second, a shot lasts seconds. The
    returned rate is the *sampled* rate, so every duration downstream stays in
    real seconds rather than silently shrinking by the stride.
    """
    # Structural black bars belong to the framing, not to the picture. Found
    # once for the whole file, since a letterbox that comes and goes is not a
    # letterbox.
    bars = detect_letterbox(path)

    capture = cv2.VideoCapture(str(path))
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    stride = max(1, int(stride))
    fps = source_fps / stride
    stats: list[FrameStats] = []
    accent_pixels: list[np.ndarray] = []
    previous: np.ndarray | None = None
    index = 0

    read = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        read += 1
        if (read - 1) % stride:
            continue
        height = int(ANALYSIS_WIDTH * frame.shape[0] / frame.shape[1])
        small = cv2.resize(frame, (ANALYSIS_WIDTH, height))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        # Colour, flatness and grade are read from the picture only; type is
        # still found across the whole frame, because a caption set into the
        # bar is a real caption.
        top = int(bars.top_pct * height)
        bottom = height - int(bars.bottom_pct * height)
        content = small[top:bottom] if bottom - top > height * 0.2 else small
        pixels = content.reshape(-1, 3)

        # Native resolution: a glyph stroke is a couple of pixels wide, and
        # resizing averages it into the background before it can be masked.
        full_h, full_w = frame.shape[:2]
        bright, accent = _text_masks(frame)
        glyph, heights, labels, kept = _glyphs(bright, accent)
        area = float(glyph.sum()) / glyph.size

        centroid = bbox = None
        glyph_h = stroke = modulation = lean = 0.0
        halo = None
        accent_share = 0.0
        if area > TEXT_AREA_FLOOR:
            ys, xs = np.nonzero(glyph)
            centroid = (float(xs.mean()) / full_w, float(ys.mean()) / full_h)
            bbox = (
                float(xs.min()) / full_w, float(ys.min()) / full_h,
                float(xs.max()) / full_w, float(ys.max()) / full_h,
            )
            glyph_h = float(np.median(heights)) / full_h if heights else 0.0
            stroke_px, modulation = _stroke_stats(glyph, labels, kept)
            stroke = stroke_px / full_h
            lean = _slant(glyph, labels, kept)
            if index % 3 == 0:       # a third of text frames is plenty to judge a treatment
                halo = _halo(frame, glyph)
            # Only accent pixels that survived as type count, so a red jacket
            # in shot cannot be mistaken for a red word.
            accent_glyph = cv2.bitwise_and(glyph, accent)
            accent_share = float(accent_glyph.sum()) / (float(glyph.sum()) or 1.0)
            if accent_glyph.sum() > 0:
                sampled = frame[accent_glyph > 0].reshape(-1, 3)
                accent_pixels.append(sampled[::5] if len(sampled) > 5000 else sampled)

        motion = zoom = 0.0
        if previous is not None:
            flow = cv2.calcOpticalFlowFarneback(previous, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            # Sampled frames are further apart, so raw flow scales with the
            # stride. Divide it back out or every strided scan looks frantic.
            motion = float(np.median(np.linalg.norm(flow, axis=2))) / stride
            yy, xx = np.mgrid[0:flow.shape[0], 0:flow.shape[1]].astype(np.float32)
            rx, ry = xx - flow.shape[1] / 2, yy - flow.shape[0] / 2
            radius = np.sqrt(rx ** 2 + ry ** 2) + 1e-6
            zoom = float(np.median((flow[:, :, 0] * rx + flow[:, :, 1] * ry) / radius)) / stride
        previous = gray

        # Type is dilated generously: what must be excluded is the halo of
        # local variance a glyph creates, not only its ink.
        type_mask = cv2.resize(cv2.dilate(glyph, np.ones((11, 11), np.uint8)),
                               (content.shape[1], content.shape[0]),
                               interpolation=cv2.INTER_NEAREST)
        modal = _modal_share(content)
        texture = _textured_share(content, ignore=type_mask)
        stats.append(FrameStats(
            t=(read - 1) / source_fps,
            mean_rgb=tuple(float(v) for v in pixels.mean(0)[::-1]),
            modal_share=modal,
            graphic=modal > GRAPHIC_MODAL_SHARE and texture < GRAPHIC_MAX_TEXTURE,
            text_area=area,
            text_centroid=centroid,
            text_bbox=bbox,
            accent_share=accent_share,
            glyph_height=glyph_h,
            stroke_width=stroke,
            stroke_modulation=modulation,
            slant=lean,
            motion=motion,
            zoom=zoom,
            halo=halo,
        ))
        index += 1

    capture.release()
    return stats, accent_pixels, fps


# --------------------------------------------------------------------------
# structure: what share of the runtime is not footage
# --------------------------------------------------------------------------


@dataclass
class Structure:
    card_share: Reading            # share of runtime on a flat graphic
    card_cadence: Reading          # seconds between breaks to a card
    plate_hex: Reading             # the card colour, as a brand slot
    static_share: Reading
    push_share: Reading


def _runs(flags: list[bool], fps: float, minimum: float = 0.25) -> list[tuple[float, float]]:
    """Contiguous true-runs, as (start, duration), discarding flickers."""
    spans: list[tuple[float, float]] = []
    start: int | None = None
    for index, flag in enumerate(flags + [False]):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            if (index - start) / fps >= minimum:
                spans.append((start / fps, (index - start) / fps))
            start = None
    return spans


def _structure(stats: list[FrameStats], fps: float) -> Structure:
    total = len(stats) / fps
    cards = _runs([s.graphic for s in stats], fps)
    on_card = sum(duration for _, duration in cards)

    plate = Reading.absent("no graphic frames")
    if cards:
        # Only *coloured* plates are a brand slot; a white product background
        # is paper, and reading it as a brand colour would be wrong.
        samples = [
            s.mean_rgb for s in stats
            if s.graphic and max(s.mean_rgb) - min(s.mean_rgb) > 25
        ]
        if samples:
            mean = np.mean(samples, 0).astype(int)
            plate = Reading(
                value="#%02X%02X%02X" % tuple(mean),
                note=f"from {len(samples)} flat coloured frames",
            )

    motions = np.array([s.motion for s in stats])
    zooms = np.array([s.zoom for s in stats])
    return Structure(
        card_share=Reading(round(on_card / total, 3), note=f"{len(cards)} card runs"),
        card_cadence=Reading(
            round(total / len(cards), 2) if cards else 0.0,
            confidence=Confidence.INFERRED if cards else Confidence.ABSENT,
            note="mean seconds of runtime per break to a card",
        ),
        plate_hex=plate,
        static_share=Reading(round(float((motions < 0.15).mean()), 3)),
        push_share=Reading(round(float((np.abs(zooms) > 0.08).mean()), 3),
                           note="share of frames with a sustained push or pull"),
    )


# --------------------------------------------------------------------------
# text: the highest-value category, and the one nobody can describe
# --------------------------------------------------------------------------


@dataclass
class TextBehaviour:
    duty_cycle: Reading            # share of runtime carrying text
    size_pct: Reading              # typical glyph height, share of frame height
    size_range: Reading            # the small and large ends, when type is mixed
    centroid: Reading              # where the block sits, normalised
    spread: Reading                # how far it moves - subtitle vs composition
    placement: Reading             # the class that spread implies
    fill_hex: Reading
    accent_hex: Reading
    accent_rate: Reading           # share of text moments that use an accent at all
    accent_share: Reading          # how much of a card is accent, when it has one
    weight: Reading                # stroke as a share of glyph height
    contrast: Reading              # stroke modulation: sans vs serif/script
    italic: Reading                # does the type lean
    typeface: Reading              # the shipped face this character resolves to
    emphasis_face: Reading         # what a stressed word would be set in
    decor: Reading                 # outline, drop shadow, or bare
    all_caps: Reading
    cards: Reading                 # how many distinct text events


def _dominant_hue(samples: list[np.ndarray]) -> Reading:
    """The accent colour, taken from the pixels rather than assumed."""
    if not samples:
        return Reading.absent("no saturated glyph pixels")
    pixels = np.concatenate(samples, 0)
    if len(pixels) > 60000:
        pixels = pixels[np.random.default_rng(0).choice(len(pixels), 60000, replace=False)]
    hsv = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    # Hue is circular, so bin it rather than averaging across the red wrap.
    bins = np.bincount((hsv[:, 0] // 6).astype(int), minlength=30)
    peak = int(bins.argmax())
    chosen = pixels[(hsv[:, 0] // 6).astype(int) == peak]
    mean = chosen.mean(0)[::-1].astype(int)
    concentration = float(bins[peak] / bins.sum())
    # A deliberate accent colour is concentrated. Pixels spread evenly across
    # the spectrum are saturated *scenery* - a red chair, a blue mug - and
    # reporting their average as a brand colour would be inventing one.
    if concentration < 0.35:
        return Reading.absent(
            f"saturated pixels are spread across hues ({concentration:.0%} in the "
            f"largest band); no deliberate accent colour"
        )
    return Reading(
        value="#%02X%02X%02X" % tuple(mean),
        confidence=Confidence.MEASURED if concentration > 0.5 else Confidence.INFERRED,
        note=f"{concentration:.0%} of accent pixels in one hue band",
    )


def _text(stats: list[FrameStats], accent_pixels: list[np.ndarray], fps: float) -> TextBehaviour:
    lit = [s for s in stats if s.text_area > TEXT_AREA_FLOOR]
    total = len(stats) / fps
    if not lit:
        absent = Reading.absent("no text found in any frame")
        return TextBehaviour(*([absent] * 18))

    duty = len(lit) / len(stats)
    events = _runs([s.text_area > TEXT_AREA_FLOOR for s in stats], fps, minimum=0.2)

    xs = np.array([s.text_centroid[0] for s in lit])
    ys = np.array([s.text_centroid[1] for s in lit])
    # Spread is the measurement that matters. Where text sits is fragile and
    # belongs to the reference; how much it *moves* is robust and is the whole
    # difference between a subtitle track and a typographic composition.
    spread = float(np.hypot(xs.std(), ys.std()))
    if spread < 0.05:
        placement = "fixed"
    elif spread < 0.13:
        placement = "banded"
    else:
        placement = "composed"

    heights = np.array([s.glyph_height for s in lit if s.glyph_height > 0])
    strokes = np.array([s.stroke_width for s in lit if s.stroke_width > 0])

    weight = Reading.absent("no glyphs measured")
    contrast = Reading.absent("no glyphs measured")
    if strokes.size and heights.size:
        # Both are frame-relative, so their ratio is resolution-independent.
        weight = Reading(round(float(np.median(strokes) / max(np.median(heights), 1e-6)), 3),
                         note="stroke width over glyph height; >0.16 reads as heavy")
        # Modulation within a glyph is what separates a sans from a serif or a
        # script. We report the spread, not a typeface name: recovering the
        # actual font from pixels is unreliable and not worth transferring.
        modulations = np.array([s.stroke_modulation for s in lit if s.stroke_modulation > 0])
        contrast = Reading(round(float(np.median(modulations)), 3) if modulations.size else 0.0,
                           confidence=Confidence.INFERRED,
                           note="stem-to-hairline contrast, 0 grotesque to 1 didone")

    leans = np.array([s.slant for s in lit if abs(s.slant) > 1e-9])
    # Roman type is not perfectly upright once it has been through a video
    # codec, so the threshold sits well clear of zero rather than at it.
    lean_reading = (
        Reading(bool(np.median(leans) > 0.12), confidence=Confidence.INFERRED,
                note=f"median lean {np.median(leans):+.3f}; >0.12 reads as italic")
        if leans.size >= 5 else Reading.absent("too few glyphs to judge lean")
    )

    face_reading = Reading.absent("no type character to resolve")
    emphasis_reading = Reading.absent("no type character to resolve")
    if strokes.size and heights.size:
        from halfheaven.render.fonts import choose, counterpart

        picked = choose(contrast=float(np.median(modulations)) if modulations.size else None,
                        italic=bool(lean_reading.value) if lean_reading else None)
        partner = counterpart(picked)
        label = lambda f: f.family + (" Italic" if f.italic else "")
        face_reading = Reading(label(picked), confidence=Confidence.INFERRED,
                               note=f"nearest shipped face to the measured character "
                                    f"({picked.genre}, contrast {picked.contrast:.2f})")
        emphasis_reading = Reading(label(partner), confidence=Confidence.INFERRED,
                                   note=f"crosses genre from the body ({partner.genre})")

    caps = Reading.absent("not enough glyphs")
    if heights.size > 20:
        # All-caps text has uniform glyph heights; mixed case scatters them
        # across ascenders, x-height and descenders.
        caps = Reading(bool(heights.std() / max(heights.mean(), 1e-6) < 0.16),
                       confidence=Confidence.INFERRED,
                       note=f"glyph-height variation {heights.std() / max(heights.mean(), 1e-6):.2f}")

    fill = Reading.absent("no bright glyph pixels")
    bright_frames = [s for s in lit if s.accent_share < 0.5]
    if bright_frames:
        fill = Reading("#FFFFFF", confidence=Confidence.INFERRED,
                       note="bright glyph mask is near-white by construction")

    # A median over every text frame is zero, because most frames of a card
    # show no accent word. The pair that actually describes the look is how
    # often an accent appears at all, and how much of the card it takes when
    # it does.
    halos = np.array([s.halo for s in lit if s.halo is not None])
    decor_reading = Reading.absent("too few captioned frames to judge an outline or a shadow")
    if len(halos) >= 5:
        darkness, leaning = float(np.median(halos[:, 0])), float(np.median(halos[:, 1]))
        decor_reading = Reading(_decor_kind(darkness, leaning), confidence=Confidence.INFERRED,
                                note=f"halo darkness {darkness:.2f}, lean {leaning:+.2f}")

    shares = np.array([s.accent_share for s in lit])
    with_accent = shares[shares > 0.01]
    return TextBehaviour(
        duty_cycle=Reading(round(duty, 3), note=f"{total * duty:.1f}s of {total:.1f}s"),
        size_pct=Reading(round(float(np.median(heights)), 4) if heights.size else 0.0,
                         note="median glyph height as a share of frame height"),
        # A single number lies about a reel that runs a huge title over a
        # small persistent sticker: the median lands between them and
        # describes neither. The spread is what says "there are two type
        # systems here", which is itself a thing worth transferring.
        size_range=Reading(
            (round(float(np.percentile(heights, 10)), 4),
             round(float(np.percentile(heights, 90)), 4)) if heights.size > 20 else None,
            confidence=Confidence.MEASURED if heights.size > 20 else Confidence.ABSENT,
            note="10th to 90th percentile of glyph height"
            if heights.size > 20 else "too few glyphs to describe a range",
        ),
        centroid=Reading((round(float(xs.mean()), 3), round(float(ys.mean()), 3))),
        spread=Reading(round(spread, 3)),
        placement=Reading(placement, confidence=Confidence.INFERRED,
                          note=f"from centroid spread {spread:.3f}"),
        fill_hex=fill,
        accent_hex=_dominant_hue(accent_pixels),
        accent_rate=Reading(round(float(len(with_accent) / len(shares)), 3),
                            note=f"{len(with_accent)}/{len(shares)} text frames carry an accent"),
        accent_share=Reading(round(float(np.median(with_accent)), 3) if with_accent.size else 0.0,
                             confidence=Confidence.MEASURED if with_accent.size
                             else Confidence.ABSENT,
                             note="median accent share among frames that have one"),
        weight=weight,
        contrast=contrast,
        italic=lean_reading,
        # Naming the face is the point of measuring character at all. Reporting
        # "contrast 0.51, leans" tells a creator nothing; "we'd set this in
        # Playfair Display Italic" is a claim they can look at and disagree with.
        typeface=face_reading,
        emphasis_face=emphasis_reading,
        decor=decor_reading,
        all_caps=caps,
        cards=Reading(len(events), note="distinct text events"),
    )


# --------------------------------------------------------------------------
# grade: sampled from photography only
# --------------------------------------------------------------------------


@dataclass
class Grade:
    lab_mean: Reading
    lab_std: Reading
    sampled_share: Reading


def _grade(path: pathlib.Path, stats: list[FrameStats]) -> Grade:
    """LAB statistics over photographic frames, ignoring graphics.

    Sampling the whole video is the bug that casts a magenta tint over any
    reference with colour cards: the cards' hue lands in the mean and gets
    applied to skin. A frame that is flat, or nearly monochrome, is design.
    """
    usable = [s for s in stats if not s.graphic]
    if len(usable) < 10:
        return Grade(Reading.absent("too few photographic frames"),
                     Reading.absent("too few photographic frames"),
                     Reading(round(len(usable) / max(len(stats), 1), 3)))

    capture = cv2.VideoCapture(str(path))
    picks = np.linspace(0, len(usable) - 1, min(60, len(usable))).astype(int)
    labs = []
    for pick in picks:
        # Seek by time, not by frame number. FrameStats.t is in real seconds
        # while `fps` here is the *sampled* rate, so multiplying the two seeks
        # to the wrong place whenever frames are strided - which silently sent
        # this function to the title cards and swung the measured grade by 15
        # units of a* without changing anything it reported about itself.
        capture.set(cv2.CAP_PROP_POS_MSEC, usable[pick].t * 1000.0)
        ok, frame = capture.read()
        if ok:
            lab = cv2.cvtColor(cv2.resize(frame, (120, 213)), cv2.COLOR_BGR2LAB)
            labs.append(lab.reshape(-1, 3).astype(np.float32))
    capture.release()

    if not labs:
        return Grade(Reading.absent("could not read frames"),
                     Reading.absent("could not read frames"), Reading(0.0))
    pixels = np.concatenate(labs, 0)
    scale = np.array([100 / 255, 1, 1])
    offset = np.array([0, -128, -128])
    mean = tuple(round(float(v), 2) for v in pixels.mean(0) * scale + offset)
    std = tuple(round(float(v), 2) for v in pixels.std(0) * scale)
    return Grade(
        lab_mean=Reading(mean, note=f"over {len(labs)} photographic frames"),
        lab_std=Reading(std),
        sampled_share=Reading(round(len(usable) / len(stats), 3),
                              note="share of frames that are photography, not graphics"),
    )


# --------------------------------------------------------------------------
# rhythm: how the cuts sit against the music
# --------------------------------------------------------------------------


@dataclass
class Rhythm:
    shot_count: Reading
    median_shot: Reading
    cuts_per_min: Reading
    tempo_bpm: Reading
    on_beat_share: Reading
    driver: Reading                # "speech" or "beat"


MIN_BEATS = 4


@functools.cache
def _beat_model():
    from beat_this.inference import Audio2Beats
    return Audio2Beats(checkpoint_path="final0", device="cpu", dbn=False)


def _beats(samples: np.ndarray, rate: int) -> np.ndarray | None:
    """Beat times from beat_this, or None when it is not installed or fails.

    Spectral flux peaks on every consonant, so under speech some peak sat near
    almost any cut. A trained tracker marks only the pulse, and marks none at
    all when there is no music.
    """
    try:
        import beat_this  # noqa: F401
    except ImportError:
        return None
    try:
        # Library chatter goes to stderr: the CLI's stdout is JSON.
        with contextlib.redirect_stdout(sys.stderr):
            beats, _ = _beat_model()(samples, rate)
    except Exception as error:
        print(f"beat tracker failed, using spectral flux: {error}", file=sys.stderr)
        return None
    return np.asarray(beats, dtype=float)


def _onsets(path: pathlib.Path) -> tuple[np.ndarray, float, bool]:
    """Beat or onset times, the dominant period, and whether a beat tracker made them.

    Uses beat_this when the `ml` extra is installed, spectral flux otherwise.
    """
    import subprocess
    import wave
    import tempfile

    from halfheaven.media.ffmpeg_bin import ffmpeg

    with tempfile.TemporaryDirectory() as tmp:
        wav = pathlib.Path(tmp) / "a.wav"
        subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(path),
                        "-ac", "1", "-ar", "22050", str(wav)],
                       check=True, capture_output=True)
        if not wav.exists():
            return np.array([]), 0.0, False
        with wave.open(str(wav)) as handle:
            rate = handle.getframerate()
            samples = np.frombuffer(handle.readframes(handle.getnframes()),
                                    dtype=np.int16).astype(np.float32) / 32768

    window, hop = 1024, 256
    if len(samples) < window * 4:
        return np.array([]), 0.0, False
    beats = _beats(samples, rate)
    if beats is not None:
        # A stray beat or two in speech is not a pulse to cut against.
        if beats.size < MIN_BEATS:
            return np.array([]), 0.0, True
        return beats, float(np.median(np.diff(beats))), True
    spectra = np.array([
        np.abs(np.fft.rfft(samples[i:i + window] * np.hanning(window)))
        for i in range(0, len(samples) - window, hop)
    ])
    flux = np.maximum(0, np.diff(spectra, axis=0)).sum(1)
    flux = (flux - flux.mean()) / (flux.std() or 1.0)
    times = np.arange(len(flux)) * hop / rate

    peaks = [
        times[i] for i in range(2, len(flux) - 2)
        if flux[i] > 1.0 and flux[i] == flux[max(0, i - 4):i + 5].max()
    ]
    centred = flux - flux.mean()
    correlation = np.correlate(centred, centred, "full")[len(flux) - 1:]
    lags = np.arange(len(correlation)) * hop / rate
    band = (lags > 0.28) & (lags < 1.2)
    period = float(lags[band][correlation[band].argmax()]) if band.any() else 0.0
    return np.array(peaks), period, False


def _rhythm(path: pathlib.Path, shots: list[Shot], has_audio: bool) -> Rhythm:
    measured = pacing(shots)
    base = dict(
        shot_count=Reading(measured.shot_count),
        median_shot=Reading(round(measured.median_shot, 2)),
        cuts_per_min=Reading(round(measured.cuts_per_min, 1)),
    )
    cuts = np.array([s.start for s in shots[1:]])
    if not has_audio:
        return Rhythm(**base,
                      tempo_bpm=Reading.absent("no audio"),
                      on_beat_share=Reading.absent("no audio"),
                      driver=Reading("beat", confidence=Confidence.INFERRED,
                                     note="no audio to cut against"))

    peaks, period, tracked = _onsets(path)
    if cuts.size == 0:
        # One continuous take has no cuts to set against anything. Only a beat
        # tracker can say whether music is there; flux fires on speech too.
        music = tracked and peaks.size > 0
        return Rhythm(**base,
                      tempo_bpm=(Reading(round(60 / period, 1), confidence=Confidence.INFERRED)
                                 if music else Reading.absent("no musical beat" if tracked
                                                              else "no cuts to time")),
                      on_beat_share=Reading.absent("one continuous take"),
                      driver=(Reading("speech", confidence=Confidence.INFERRED,
                                      note="one continuous take with no music")
                              if tracked and not music
                              else Reading.absent("one continuous take: no cuts to place")))
    if peaks.size == 0 and tracked:
        # A beat tracker finding no pulse means no music: the words drive it.
        return Rhythm(**base,
                      tempo_bpm=Reading.absent("no musical beat"),
                      on_beat_share=Reading.absent("no musical beat"),
                      driver=Reading("speech", confidence=Confidence.INFERRED,
                                     note="no musical beat under the cuts"))
    if peaks.size == 0:
        return Rhythm(**base,
                      tempo_bpm=Reading.absent("no onsets detected"),
                      on_beat_share=Reading.absent("no onsets detected"),
                      driver=Reading.absent("no onsets detected"))

    offsets = np.array([np.abs(peaks - cut).min() for cut in cuts])
    share = float((offsets < 0.12).mean())
    # This is the honest version of the speech/montage split. Asking whether a
    # file has an audio track says nothing - a montage has music. Asking how
    # tightly the cuts sit on the beat separates them cleanly: a montage lands
    # nearly every cut, a talking head lands the ones it can.
    driver = "beat" if share >= 0.8 else "speech"
    return Rhythm(**base,
                  tempo_bpm=Reading(round(60 / period, 1) if period else 0.0,
                                    confidence=Confidence.INFERRED),
                  on_beat_share=Reading(round(share, 3),
                                        note=f"{int(share * len(cuts))}/{len(cuts)} cuts within 120ms"),
                  driver=Reading(driver, confidence=Confidence.INFERRED,
                                 note=f"from on-beat share {share:.2f}"))


# --------------------------------------------------------------------------


@dataclass
class Fingerprint:
    source: str
    duration: float
    width: int
    height: int
    rhythm: Rhythm
    structure: Structure
    text: TextBehaviour
    grade: Grade
    depth: "Depth | None" = None

    def as_dict(self) -> dict:
        def unpack(value):
            if isinstance(value, Reading):
                return {"value": value.value, "confidence": value.confidence.value,
                        "note": value.note}
            if dataclasses.is_dataclass(value):
                return {f.name: unpack(getattr(value, f.name))
                        for f in dataclasses.fields(value)}
            return value
        return unpack(self)


@dataclass
class Depth:
    """Whether the text sits in front of the subject or behind them."""

    behind_subject: Reading
    subject_share: Reading
    tested_frames: Reading


def extract_fingerprint(path: str | pathlib.Path, with_depth: bool = False,
                        stride: int = 1) -> Fingerprint:
    """Everything we can recover about how a reference was edited."""
    path = pathlib.Path(path)
    info = probe(path)
    stats, accent_pixels, fps = _scan(path, stride=stride)
    shots = detect_shots(path)

    print_ready = Fingerprint(
        source=path.name,
        duration=round(info.duration, 2),
        width=info.width,
        height=info.height,
        rhythm=_rhythm(path, shots, info.has_audio),
        structure=_structure(stats, fps),
        text=_text(stats, accent_pixels, fps),
        grade=_grade(path, stats),
    )
    if with_depth:
        from halfheaven.analyze.depth import measure_depth

        print_ready.depth = measure_depth(path, stats, shots, fps)
    return print_ready


# --------------------------------------------------------------------------
# reading it as a person
# --------------------------------------------------------------------------

_MARK = {Confidence.MEASURED: "  ", Confidence.INFERRED: "~ ", Confidence.ABSENT: "! "}


def report(print_ready: Fingerprint) -> str:
    """The fingerprint as text, with every reading's standing shown.

    The markers matter as much as the numbers: `~` is inferred from another
    measurement, `!` is something we looked for and did not find. A reader who
    cannot see which is which will treat a fallback as a finding.
    """
    lines = [
        f"{print_ready.source}",
        f"{print_ready.width}x{print_ready.height}  {print_ready.duration}s",
        "",
        "  measured   ~ inferred   ! looked for, not found",
    ]

    def walk(section, indent: int = 0) -> None:
        for entry in dataclasses.fields(section):
            value = getattr(section, entry.name)
            if isinstance(value, Reading):
                shown = "—" if value.confidence is Confidence.ABSENT else value.value
                lines.append(f"{' ' * indent}{_MARK[value.confidence]}"
                             f"{entry.name:<16}{str(shown):<24}  {value.note}")
            elif dataclasses.is_dataclass(value):
                lines.append("")
                lines.append(f"{' ' * indent}[{entry.name}]")
                walk(value, indent + 2)

    walk(print_ready)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Measure how a reference video was edited.")
    parser.add_argument("video", help="the reel to read")
    parser.add_argument("--depth", action="store_true",
                        help="also ask whether text sits behind the subject "
                             "(loads SAM2; slow)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a report")
    parser.add_argument("--stride", type=int, default=1,
                        help="sample every nth frame; 3 is about three times faster "
                             "and changes nothing measured here")
    args = parser.parse_args(argv)

    result = extract_fingerprint(args.video, with_depth=args.depth, stride=args.stride)
    if args.json:
        import json

        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
