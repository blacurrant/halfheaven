"""Does the text sit in front of the subject, or behind them?

This is the one property of a caption that cannot be recovered from the text
alone, and it is the difference between a title that reads as an overlay and
one that reads as part of the scene. It is also the most-requested effect in
short form, so a reference that uses it must be measured as using it.

The test is a subtraction. Take the frames where text and subject share space,
and ask what the text does there:

    text pixels landing on the subject   -> the text is in front
    text bounding box over the subject,
    but no text pixels on them           -> the text is behind

The second case is the whole trick: a word drawn behind someone has a bite
taken out of it in exactly their silhouette, so its ink stops at their edge
while its box carries on across them. Nothing else in an edit produces that
pattern, which is what makes a fairly crude measurement decisive.

Segmentation is expensive, so only shots that actually have text over a
plausible subject are ever handed to the model.
"""
from __future__ import annotations

import pathlib
import subprocess
import tempfile
from typing import TYPE_CHECKING

import cv2
import numpy as np

from halfheaven.analyze.shots import Shot
from halfheaven.media.ffmpeg_bin import ffmpeg

if TYPE_CHECKING:
    from halfheaven.analyze.fingerprint import Depth, FrameStats

# How many shots to segment. Each costs a model pass, and the answer is a
# yes/no that stabilises quickly, so a handful is plenty.
MAX_SHOTS = 4

# A text pixel this far inside the subject is standing on them rather than
# grazing an edge. Anti-aliasing and a soft matte both blur the boundary, and
# without the erosion every overlay would look like it was in front.
SUBJECT_EROSION = 7

# How much thinner the ink must get over the subject before we call it
# occluded. Text drawn in front keeps roughly the same density either side of
# the silhouette; text drawn behind stops dead at it. Measured on the two
# references, in-front shots land near 3.0 and occluded ones below 0.3, so the
# threshold sits in a wide empty gap rather than on a cliff.
OCCLUSION_RATIO = 0.6


def _shot_of(t: float, shots: list[Shot]) -> Shot | None:
    for shot in shots:
        if shot.start <= t < shot.end:
            return shot
    return None


def _candidate_shots(stats: list["FrameStats"], shots: list[Shot]) -> list[Shot]:
    """Shots worth segmenting: the ones that hold text on screen the longest.

    Ranking by how *big* the text looks would be the obvious choice and is
    exactly wrong. A word drawn behind someone has part of itself cut away, so
    the shots that use the effect measure smaller than the ones that do not -
    the heuristic would rank the answer last and then discard it. Dwell has no
    such bias: a caption that stays up is worth a model pass however much of it
    the subject happens to be covering.
    """
    held: dict[tuple[float, float], int] = {}
    for frame in stats:
        if frame.text_bbox is None:
            continue
        shot = _shot_of(frame.t, shots)
        if shot is None:
            continue
        key = (shot.start, shot.end)
        held[key] = held.get(key, 0) + 1

    ranked = sorted(held.items(), key=lambda item: -item[1])
    return [Shot(start=start, end=end) for (start, end), frames in ranked[:MAX_SHOTS]
            if frames >= 8]


def _clip(video: pathlib.Path, shot: Shot, out: pathlib.Path) -> pathlib.Path:
    """Cut one shot out, because SAM2's temporal memory is void across a cut."""
    subprocess.run(
        [ffmpeg(), "-v", "error", "-y", "-ss", str(shot.start),
         "-t", str(max(0.3, shot.duration)), "-i", str(video),
         "-an", "-c:v", "libx264", "-crf", "20", str(out)],
        check=True, capture_output=True,
    )
    return out


def measure_depth(
    video: pathlib.Path,
    stats: list["FrameStats"],
    shots: list[Shot],
    fps: float,
    segmenter=None,
) -> "Depth":
    """Whether this reference draws its text behind the subject."""
    from halfheaven.analyze.fingerprint import Confidence, Depth, Reading, _text_masks, _glyphs

    candidates = _candidate_shots(stats, shots)
    if not candidates:
        return Depth(
            behind_subject=Reading.absent("no shot has text large enough to overlap a subject"),
            subject_share=Reading.absent("not segmented"),
            tested_frames=Reading(0),
        )

    if segmenter is None:
        from halfheaven.analyze.sam2_segmenter import Sam2Segmenter

        segmenter = Sam2Segmenter()

    # Depth is a property of a shot, not of a video: a reel can put text
    # behind someone in one beat and over them in the next. Averaging the two
    # reports neither. What the fingerprint needs to know is whether the
    # reference uses the effect *at all*, so each shot is judged separately.
    per_shot: list[tuple[float, float, int]] = []   # start, ink ratio, frames
    subject_sizes: list[float] = []
    tested = 0

    with tempfile.TemporaryDirectory() as tmp:
        for index, shot in enumerate(candidates):
            clip = _clip(video, shot, pathlib.Path(tmp) / f"shot{index}.mp4")
            capture = cv2.VideoCapture(str(clip))
            frames = []
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                frames.append(frame)
            capture.release()
            if not frames:
                continue

            height, width = frames[0].shape[:2]
            masks = segmenter.masks_for_video(clip, (width, height))

            shot_ratios: list[float] = []
            for frame, mask in zip(frames, masks):
                subject = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)
                subject = (subject > 127).astype(np.uint8)
                share = float(subject.mean())
                # No subject, or a mask that swallowed the frame: either way
                # there is no foreground/background relationship to measure.
                if not 0.02 < share < 0.85:
                    continue

                glyph, _, _, _ = _glyphs(*_text_masks(frame))
                if glyph.sum() < 200:
                    continue
                ys, xs = np.nonzero(glyph)
                box = np.zeros_like(glyph)
                box[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = 1

                core = cv2.erode(subject, np.ones((SUBJECT_EROSION,) * 2, np.uint8))
                overlap = float((box & core).sum())
                if overlap < 0.02 * box.sum():
                    continue  # the text never reaches them; says nothing either way

                # A word that runs behind someone reappears on the far side.
                # Without this, a caption sitting beside a subject scores as
                # perfectly occluded - its box clips them, none of its ink
                # does, and the density test reads zero. Requiring ink both
                # left and right of the subject is what distinguishes "behind"
                # from "next to".
                subject_columns = np.nonzero(core.any(axis=0))[0]
                ink_columns = np.nonzero(glyph.any(axis=0))[0]
                if not subject_columns.size or not ink_columns.size:
                    continue
                left = (ink_columns < subject_columns.min()).sum()
                right = (ink_columns > subject_columns.max()).sum()
                if min(left, right) < 0.12 * ink_columns.size:
                    continue  # the text sits beside them, not across them

                # Comparing raw ink to overlapped area would call any sparse
                # caption "behind", because a scattered word's bounding box is
                # mostly empty. What settles it is whether the ink thins out
                # *specifically* where the subject is: measure its density on
                # the subject against its density elsewhere in the same box.
                outside = float((box & ~core.astype(bool)).sum())
                ink_on = float((glyph & core).sum())
                ink_off = float((glyph & box).sum()) - ink_on
                if outside < 1 or ink_off < 150:
                    continue      # nothing to compare against
                density_on = ink_on / overlap
                density_off = ink_off / outside
                shot_ratios.append(density_on / max(density_off, 1e-9))
                subject_sizes.append(share)
                tested += 1
            if shot_ratios:
                per_shot.append((shot.start, float(np.median(shot_ratios)), len(shot_ratios)))

    if not per_shot:
        return Depth(
            behind_subject=Reading.absent("text and subject never overlapped"),
            subject_share=Reading.absent("no usable frames"),
            tested_frames=Reading(tested),
        )

    occluded = [shot for shot in per_shot if shot[1] < OCCLUSION_RATIO and shot[2] >= 5]
    detail = ", ".join(f"{start:.1f}s={ratio:.2f}({count}f)" for start, ratio, count in per_shot)
    return Depth(
        behind_subject=Reading(
            bool(occluded),
            confidence=Confidence.MEASURED if tested >= 8 else Confidence.INFERRED,
            note=f"{len(occluded)}/{len(per_shot)} shots occlude their text; "
                 f"per-shot density ratio (on subject / off subject) {detail}",
        ),
        subject_share=Reading(round(float(np.median(subject_sizes)), 3),
                              note="median share of frame occupied by the subject"),
        tested_frames=Reading(tested),
    )
