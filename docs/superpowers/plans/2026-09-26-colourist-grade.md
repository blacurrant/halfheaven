# Colourist Grade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single statistical grade LUT with a colourist-style grade: correct the footage, read the reference's look as named controls per zone (subject, background, skin), and render it as three LUTs joined through the existing mattes.

**Architecture:**
- `analyze/zones.py` reads a `ZoneLook` from any footage given masks. The reference gets its masks from MediaPipe parts; the takes get them from their own mattes.
- `plan/colourist.py` turns a take look and a reference look into bounded `GradeControls`.
- `render/lut.py` bakes the controls into subject, background and skin `.cube` files.
- The finish pass in `render/video.py` composites the three LUT outputs through a choked subject matte and the skin matte.
- Without zones or mattes, today's single LUT runs unchanged.

**Tech Stack:** Python 3.11, numpy, OpenCV (float LAB), pydantic v2, ffmpeg filtergraphs (`lut3d`, `alphamerge`, `overlay`, `erosion`, `gblur`), MediaPipe multiclass selfie segmenter, pytest.

**Spec:** `docs/superpowers/specs/2026-09-26-colourist-grade-design.md`

## Global Constraints

- Python is the repo venv: `PY="/Users/landerstudio/Desktop/untitled folder/halfheaven/.venv/bin/python"`. Run every test from `packages/pipeline` inside the workspace: `cd packages/pipeline && "$PY" -m pytest tests/<file> -q`.
- Pixel math is in OpenCV float LAB: an RGB float32 image in 0–1 goes through `cv2.COLOR_RGB2LAB`, giving L 0–100 and a, b roughly ±127. This is what `render/lut.py` already uses.
- **Rule 1:** the creator's face keeps its own brightness. The skin LUT pins L to the corrected L. Separation is reached by moving the background, never by lightening or darkening skin toward the reference's person.
- **Rule 2:** every control is bounded. White balance ±12° × 0.8. Exposure anchor 0.7–1.5. Tone-curve slope 0.12–1.6. Saturation: subject 0.85–1.15, background 0.8–1.3. Skin richness 0.85–1.3.
- **Rule 3:** strength 0 is the identity. `GradeProfile.strength` (the chat's `grade.strength` knob) scales every control.
- **Rule 4:** no mattes, no zones. If the reference has no person, or any take lacks a subject or skin matte, or a matte is missing at render time, today's global LUT runs.
- Order inside the finish pass stays: grade → background replacement → letterbox → captions.
- Grade matte defaults: choke 0.5% and feather 0.5% of frame height.
- The CLI keeps printing `grade LAB mean=` and `grade: target LAB mean=` exactly as now, because `apps/web/src/lib/pipeline.ts` parses them for the studio's colour swatches.
- Do not edit anything under `apps/web`. Other sessions work there.
- Add no new dependencies. RVM stays server-side (GPL-3.0).
- Evaluate across every reference in the matrix. Never tune for one reel.

## Review Focus

- **A take's matte is missing on disk at render time** (for example, a cleaned work dir). The render falls back to the single LUT instead of crashing. Pinned by `test_a_missing_matte_falls_back_to_the_single_lut` in Task 6.
- **A matte video is smaller than its take** (4K take, mattes written at ≤1280). Zones are read at the take's downscaled size. Pinned by `test_a_matte_smaller_than_its_take_is_scaled_to_it` in Task 1.
- **A take shows no skin** (back to camera, hands only). No white balance, anchor 1 and skin richness 1, and the LUTs are still valid. Pinned by `test_a_take_with_no_skin_in_view_gets_no_skin_moves` in Task 4.
- **Letterbox, behind-captions, background replacement and the zone grade all at once.** The subject matte is read once and the grade comes before the letterbox. Pinned by `test_the_subject_matte_is_read_once_for_grade_captions_and_backdrop` in Task 6.
- **A reference whose person is tiny** (a wide shot) or rarely in frame gets no zones and keeps the single grade. Pinned by `test_a_reference_whose_person_is_tiny_has_no_zones` (Task 1) and `test_no_zones_means_no_colourist_grade` (Task 8).

---

### Task 0: Workspace

**Files:** none created. Moves the spec and this plan onto the feature branch.

- [ ] **Step 1: Create the workspace.** Use superpowers:using-git-worktrees to create an isolated workspace on a new branch named `colourist-grade` from `main`. Every later path is relative to that workspace.
- [ ] **Step 2: Move the spec and plan in, and commit.** Both files are untracked in the main checkout.

```bash
MAIN="/Users/landerstudio/Desktop/untitled folder/halfheaven"
mkdir -p docs/superpowers/specs docs/superpowers/plans
mv "$MAIN/docs/superpowers/specs/2026-09-26-colourist-grade-design.md" docs/superpowers/specs/
mv "$MAIN/docs/superpowers/plans/2026-09-26-colourist-grade.md" docs/superpowers/plans/
git add docs/superpowers
git commit -m "docs: colourist grade spec and plan"
```

- [ ] **Step 3: Baseline.** Run `cd packages/pipeline && "$PY" -m pytest -q`. Expected: all pass. Note the count.

---

### Task 1: Reading zones

**Files:**
- Modify: `packages/pipeline/halfheaven/schemas.py`. Add `ZoneTone`, `SkinTone` and `ZoneLook` directly above `class Look`, and `zones` to `GradeProfile`.
- Create: `packages/pipeline/halfheaven/analyze/zones.py`
- Create: `packages/pipeline/tests/zone_fakes.py` (shared test stand-ins)
- Test: `packages/pipeline/tests/test_zones.py`

**Interfaces:**
- Produces:
  - `schemas.ZoneTone(l_quantiles: list[float] (101), mean_l: float, median_chroma: float, tints: list[tuple[float, float]] (6), shadow_tint_a: float | None)`
  - `schemas.SkinTone(ab: tuple[float, float], mean_l: float, median_l: float)`
  - `schemas.ZoneLook(subject: ZoneTone, background: ZoneTone, skin: SkinTone | None)`
  - `GradeProfile.zones: ZoneLook | None`
  - `analyze.zones`: `BANDS`, `BAND_CENTRES`, `to_lab(bgr) -> lab`, `shrink(bgr, max_side=640) -> bgr`, `read_zone_look(samples) -> ZoneLook | None`, `summarise(look | None) -> dict[str, float | None]` (keys `face_above_background`, `background_l`, `skin_chroma`, `skin_hue`, `shadow_tint`), `take_zone_look(takes: list[str], mattes: dict[str, TakeMatte]) -> ZoneLook | None`, `reference_zone_look(path, times: list[float], parts=None) -> ZoneLook | None`
  - `tests/zone_fakes.py`: `WIDE`, `BARS`, `Bright`, `ellipse_parts`, `tiny_parts`

- [ ] **Step 1: Add the schema models.** In `schemas.py`, directly above `class Look(BaseModel):`, add:

```python
class ZoneTone(BaseModel):
    """How one zone of a picture is lit and coloured, in OpenCV float LAB (L 0-100)."""

    # L at percentiles 0..100 of the zone's pixels.
    l_quantiles: list[float] = Field(min_length=101, max_length=101)
    mean_l: float
    median_chroma: float
    # Mean (a, b) of the zone's near-neutral pixels in each L band of
    # analyze.zones.BANDS: the split tone. A thin band takes the zone's mean.
    tints: list[tuple[float, float]] = Field(min_length=6, max_length=6)
    # Mean a* of near-neutral pixels darker than L 20; None when too few.
    shadow_tint_a: float | None = None


class SkinTone(BaseModel):
    ab: tuple[float, float]
    mean_l: float
    median_l: float


class ZoneLook(BaseModel):
    """A picture read as the subject, the room behind them, and skin."""

    subject: ZoneTone
    background: ZoneTone
    skin: SkinTone | None = None
```

In `class GradeProfile`, after `strength`, add:

```python
    # The reference read per zone (subject, background, skin). None when it
    # shows no person often enough; the colourist grade then does not run.
    zones: ZoneLook | None = None
```

- [ ] **Step 2: Write the shared test stand-ins.** Create `tests/zone_fakes.py`:

```python
"""Stand-ins shared by the zone-grade tests: fixtures, fake models, synthetic looks."""
import pathlib

import numpy as np

from halfheaven.analyze.matte import BACKGROUND, FACE_SKIN

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
# 640x360, 25fps, 4.4s: a skin-coloured ellipse (228,196,172) on a dark, near-neutral room.
WIDE = FIXTURES / "wide_subject_moves.mp4"
BARS = FIXTURES / "three_shots_at_1.0_3.0.mp4"      # 320x568, 4.5s


class Bright:
    """Segmenter stand-in: the wide fixture's subject is the only bright thing in it."""

    def mask_for(self, frame):
        return np.where(frame.max(axis=2) > 150, 255, 0).astype(np.uint8)


def ellipse_parts(rgb, t_ms):
    """MediaPipe stand-in: the bright ellipse is a person, all of it face skin."""
    return np.where(rgb.max(axis=2) > 150, FACE_SKIN, BACKGROUND).astype(np.uint8)


def tiny_parts(rgb, t_ms):
    """MediaPipe stand-in: a person far too small to read a grade from."""
    classes = np.full(rgb.shape[:2], BACKGROUND, np.uint8)
    classes[:10, :10] = FACE_SKIN
    return classes
```

- [ ] **Step 3: Write the failing tests.** Create `tests/test_zones.py`:

```python
"""Reading a picture as zones: the subject, the room behind them, and skin."""
import subprocess

import numpy as np
import pytest

from halfheaven.analyze.segment import write_matte_video
from halfheaven.analyze.zones import read_zone_look, reference_zone_look, summarise, take_zone_look
from halfheaven.media.ffmpeg_bin import ffmpeg
from halfheaven.schemas import TakeMatte
from tests.zone_fakes import WIDE, Bright, ellipse_parts, tiny_parts

TIMES = [0.1 + 0.3 * i for i in range(14)]      # inside the 4.4s fixture


def split_frame(subject_lab=(60.0, 12.0, 14.0), background_lab=(18.0, 6.0, 1.0)):
    """100x100 LAB: left half subject, right half background, top-left quarter skin."""
    lab = np.zeros((100, 100, 3), np.float32)
    lab[:, :50] = subject_lab
    lab[:, 50:] = background_lab
    subject = np.zeros((100, 100), bool)
    subject[:, :50] = True
    skin = np.zeros((100, 100), bool)
    skin[:50, :50] = True
    return lab, subject, ~subject, skin


def test_each_zone_is_read_on_its_own():
    look = read_zone_look([split_frame()])
    assert look.subject.mean_l == pytest.approx(60.0)
    assert look.background.l_quantiles[50] == pytest.approx(18.0)
    assert look.skin.ab == pytest.approx((12.0, 14.0))


def test_the_split_tone_is_read_from_near_neutral_pixels():
    look = read_zone_look([split_frame()])
    assert look.background.tints[1] == pytest.approx((6.0, 1.0))    # the 12-25 band holds L 18
    assert look.background.shadow_tint_a == pytest.approx(6.0)
    # the subject's chroma is 18.4, not near-neutral, so it carries no tint
    assert look.subject.tints[3] == pytest.approx((0.0, 0.0))


def test_the_summary_is_what_the_scorecard_compares():
    summary = summarise(read_zone_look([split_frame()]))
    assert summary["face_above_background"] == pytest.approx(42.0)
    assert summary["background_l"] == pytest.approx(18.0)
    assert summary["skin_chroma"] == pytest.approx(18.44, abs=0.01)
    assert summary["skin_hue"] == pytest.approx(49.4, abs=0.1)
    assert summary["shadow_tint"] == pytest.approx(6.0)


def test_too_little_subject_reads_nothing():
    lab, subject, background, skin = split_frame()
    subject[:] = False
    subject[:10, :10] = True
    assert read_zone_look([(lab, subject, background, skin)]) is None


def test_without_skin_the_zones_are_still_read():
    lab, subject, background, skin = split_frame()
    look = read_zone_look([(lab, subject, background, np.zeros_like(skin))])
    assert look.skin is None
    summary = summarise(look)
    assert summary["skin_hue"] is None and summary["background_l"] == pytest.approx(18.0)


def test_a_take_is_read_through_its_own_mattes(tmp_path):
    matte = write_matte_video(WIDE, Bright(), tmp_path / "m.mp4", feather=0)
    look = take_zone_look([str(WIDE)], {str(WIDE): TakeMatte(subject=str(matte), skin=str(matte))})
    assert look.subject.mean_l > 70 and look.background.mean_l < 25
    assert look.skin is not None


def test_a_matte_smaller_than_its_take_is_scaled_to_it(tmp_path):
    full = write_matte_video(WIDE, Bright(), tmp_path / "m.mp4", feather=0)
    small = tmp_path / "small.mp4"
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(full), "-vf", "scale=320:180",
                    "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(small)], check=True)
    look = take_zone_look([str(WIDE)], {str(WIDE): TakeMatte(subject=str(small), skin=str(small))})
    assert look.subject.mean_l > 70 and look.background.mean_l < 25


def test_a_take_without_a_matte_is_not_read():
    assert take_zone_look([str(WIDE)], {}) is None


def test_a_reference_is_read_through_its_parts():
    look = reference_zone_look(WIDE, TIMES, parts=ellipse_parts)
    assert look.subject.mean_l > 70 and look.background.mean_l < 25
    assert look.skin is not None


def test_a_reference_whose_person_is_tiny_has_no_zones():
    assert reference_zone_look(WIDE, TIMES, parts=tiny_parts) is None
```

- [ ] **Step 4: Run them to see them fail.** Run `cd packages/pipeline && "$PY" -m pytest tests/test_zones.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'halfheaven.analyze.zones'`.

- [ ] **Step 5: Implement.** Create `halfheaven/analyze/zones.py`:

```python
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
```

- [ ] **Step 6: Run the tests to see them pass.** Run `"$PY" -m pytest tests/test_zones.py -q`. Expected: 10 passed.

- [ ] **Step 7: Commit.**

```bash
git add packages/pipeline/halfheaven/schemas.py packages/pipeline/halfheaven/analyze/zones.py \
        packages/pipeline/tests/zone_fakes.py packages/pipeline/tests/test_zones.py
git commit -m "feat(grade): read footage as subject, background and skin zones"
```

---

### Task 2: The fingerprint reads zones, and the profile carries them

**Files:**
- Modify: `packages/pipeline/halfheaven/analyze/fingerprint.py`. Change the `Grade` dataclass (~line 761), add `_grade_zones` after `_grade`, add `zone_look` to the `Fingerprint` dataclass, and update `extract_fingerprint`.
- Modify: `packages/pipeline/halfheaven/plan/typography.py`, in `_apply_grade`.
- Test: `packages/pipeline/tests/test_grade_zone_readings.py`

**Interfaces:**
- Consumes: `analyze.zones.reference_zone_look`, `analyze.zones.summarise`, `schemas.ZoneLook` (Task 1).
- Produces:
  - `fingerprint._grade_zones(path, stats, parts=None) -> tuple[dict[str, Reading], ZoneLook | None]`
  - `Grade` gains readings `face_above_background`, `background_l`, `skin_chroma`, `skin_hue`, `shadow_tint`.
  - `Fingerprint.zone_look: dict | None`, serialised as the top-level `"zone_look"` key by `as_dict()`.
  - `apply_fingerprint` sets `profile.grade.zones`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_grade_zone_readings.py`:

```python
"""The reference's grade, read per zone, and carried into the style profile."""
from halfheaven.analyze.fingerprint import Confidence, FrameStats, _grade_zones
from halfheaven.plan.typography import apply_fingerprint
from halfheaven.schemas import StyleProfile, ZoneLook
from tests.zone_fakes import WIDE, ellipse_parts


def photo(t):
    return FrameStats(t=t, mean_rgb=(0.0, 0.0, 0.0), modal_share=0.1, graphic=False, text_area=0.0,
                      text_centroid=None, text_bbox=None, accent_share=0.0, glyph_height=0.0,
                      stroke_width=0.0, stroke_modulation=0.0, slant=0.0, motion=0.0, zoom=1.0)


def test_the_grade_reads_the_face_against_the_room():
    readings, look = _grade_zones(WIDE, [photo(0.1 + 0.3 * i) for i in range(14)], parts=ellipse_parts)
    assert readings["face_above_background"].value > 45
    assert readings["skin_hue"].confidence is Confidence.MEASURED
    assert isinstance(look, ZoneLook) and len(look.subject.l_quantiles) == 101


def test_without_enough_photography_the_zone_readings_are_absent():
    readings, look = _grade_zones(WIDE, [photo(0.5)] * 3, parts=ellipse_parts)
    assert look is None
    assert all(r.confidence is Confidence.ABSENT for r in readings.values())


def test_the_profile_carries_the_reference_zones():
    _, look = _grade_zones(WIDE, [photo(0.1 + 0.3 * i) for i in range(14)], parts=ellipse_parts)
    reading = lambda value: {"value": value, "confidence": "measured", "note": ""}
    fingerprint = {"grade": {"lab_mean": reading([30.0, 4.0, 6.0]), "lab_std": reading([15.0, 8.0, 9.0])},
                   "zone_look": look.model_dump()}
    profile = apply_fingerprint(StyleProfile(), fingerprint)
    assert profile.grade.zones == look


def test_a_profile_without_zones_keeps_none():
    reading = lambda value: {"value": value, "confidence": "measured", "note": ""}
    fingerprint = {"grade": {"lab_mean": reading([30.0, 4.0, 6.0]), "lab_std": reading([15.0, 8.0, 9.0])}}
    assert apply_fingerprint(StyleProfile(), fingerprint).grade.zones is None
```

- [ ] **Step 2: Run them to see them fail.** Run `"$PY" -m pytest tests/test_grade_zone_readings.py -q`. Expected: FAIL with `ImportError: cannot import name '_grade_zones'`.

- [ ] **Step 3: Implement in `fingerprint.py`.**

Add to the imports (top of file, beside the other `halfheaven` imports):

```python
from halfheaven.analyze.zones import reference_zone_look, summarise
from halfheaven.schemas import ZoneLook
```

Replace the `Grade` dataclass with:

```python
ZONE_READINGS = ("face_above_background", "background_l", "skin_chroma", "skin_hue", "shadow_tint")


def _not_read() -> "Reading":
    return Reading.absent("not measured")


@dataclass
class Grade:
    lab_mean: Reading
    lab_std: Reading
    sampled_share: Reading
    # Read per zone (see analyze/zones.py): how far the face stands above the
    # room, how dark the room is, how rich and which hue the skin is, and the
    # red/green lean of the room's near-neutral shadows.
    face_above_background: Reading = field(default_factory=_not_read)
    background_l: Reading = field(default_factory=_not_read)
    skin_chroma: Reading = field(default_factory=_not_read)
    skin_hue: Reading = field(default_factory=_not_read)
    shadow_tint: Reading = field(default_factory=_not_read)
```

Add directly after `_grade`:

```python
def _grade_zones(path: pathlib.Path, stats: list[FrameStats],
                 parts=None) -> tuple[dict[str, Reading], ZoneLook | None]:
    """The subject, the room and skin, read on the photographic frames `_grade` reads.

    Absent rather than guessed when the reference shows no person often
    enough, or when subject separation is not installed here.
    """
    usable = [s for s in stats if not s.graphic]
    look, why = None, "too few photographic frames"
    if len(usable) >= 10:
        picks = np.unique(np.linspace(0, len(usable) - 1, min(60, len(usable))).astype(int))
        try:
            look = reference_zone_look(path, [usable[p].t for p in picks], parts=parts)
            why = "no person in enough photographic frames"
        except (ImportError, OSError, RuntimeError) as error:
            why = f"subject separation unavailable: {error}"
    if look is None:
        return {name: Reading.absent(why) for name in ZONE_READINGS}, None
    readings = {name: Reading.absent("too few pixels to read") if value is None else Reading(value)
                for name, value in summarise(look).items()}
    return readings, look
```

In `class Fingerprint`, after `depth: "Depth | None" = None`, add:

```python
    # The reference's zones in full, for the colourist planner. Kept out of
    # `grade` because the /lab readout lists every grade reading.
    zone_look: dict | None = None
```

In `extract_fingerprint`, replace `grade=_grade(path, stats),` with the lines below. Compute them before the `Fingerprint(...)` call:

```python
    zone_readings, zone_look = _grade_zones(path, stats)
```

Then pass these arguments:

```python
        grade=dataclasses.replace(_grade(path, stats), **zone_readings),
        zone_look=zone_look.model_dump() if zone_look else None,
```

- [ ] **Step 4: Implement in `typography.py`.** Change the import `from halfheaven.schemas import StyleProfile, TypePlan` to `from halfheaven.schemas import StyleProfile, TypePlan, ZoneLook`. In `_apply_grade`, replace the final `return` with:

```python
    zones = fingerprint.get("zone_look")
    return profile.model_copy(update={"grade": profile.grade.model_copy(update={
        "measured": True,
        "lab_mean": tuple(float(v) for v in mean),
        "lab_std": tuple(float(v) for v in spread),
        "zones": ZoneLook.model_validate(zones) if zones else None,
    })})
```

- [ ] **Step 5: Run the new and old tests.** Run `"$PY" -m pytest tests/test_grade_zone_readings.py tests/test_fingerprint.py tests/test_typography.py -q`. Expected: all pass. `test_fingerprint.py` now also runs MediaPipe on its fixtures; where no person is found, the zone readings are simply absent.

- [ ] **Step 6: Commit.**

```bash
git add packages/pipeline/halfheaven/analyze/fingerprint.py packages/pipeline/halfheaven/plan/typography.py \
        packages/pipeline/tests/test_grade_zone_readings.py
git commit -m "feat(grade): the fingerprint reads the reference per zone"
```

---

### Task 3: Scorecard traits for the zones

**Files:**
- Modify: `packages/pipeline/halfheaven/analyze/compare.py`. Add `_angle` after `_lab_distance`, and five `Trait` rows after the `lab_mean` row.
- Test: `packages/pipeline/tests/test_compare.py` (new; no scorecard tests exist yet)

**Interfaces:**
- Consumes: the `Grade` readings from Task 2.
- Produces: `compare._angle(a, b) -> float`, and the traits `grade.face_above_background`, `grade.background_l`, `grade.skin_chroma`, `grade.skin_hue` and `grade.shadow_tint`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_compare.py`:

```python
"""The scorecard's zone traits."""
from types import SimpleNamespace

from halfheaven.analyze.compare import Verdict, _angle, compare
from halfheaven.analyze.fingerprint import Reading


def grade_only(source, **values):
    readings = {name: (Reading.absent("none") if value is None else Reading(value))
                for name, value in values.items()}
    return SimpleNamespace(source=source, grade=SimpleNamespace(**readings))


def rows_by_field(card):
    return {row.trait.field: row for row in card.rows if row.trait.group == "grade"}


def test_hue_distance_wraps_round_the_circle():
    assert _angle(350.0, 10.0) == 20.0
    assert _angle(-170.0, 170.0) == 20.0


def test_close_zone_readings_match_and_far_ones_miss():
    ours = grade_only("out", face_above_background=20.0, background_l=14.0, skin_chroma=28.0,
                      skin_hue=43.5, shadow_tint=8.2)
    theirs = grade_only("ref", face_above_background=28.8, background_l=8.9, skin_chroma=29.8,
                        skin_hue=31.9, shadow_tint=7.1)
    rows = rows_by_field(compare(ours, theirs))
    assert rows["background_l"].verdict is Verdict.MATCH          # 5.1 <= 6
    assert rows["face_above_background"].verdict is Verdict.NEAR  # 8.8 <= 12
    assert rows["skin_chroma"].verdict is Verdict.MATCH
    assert rows["skin_hue"].verdict is Verdict.NEAR               # 11.6 <= 12
    assert rows["shadow_tint"].verdict is Verdict.MATCH


def test_a_zone_reading_missing_on_either_side_is_unscored():
    ours = grade_only("out", face_above_background=None, background_l=14.0, skin_chroma=None,
                      skin_hue=None, shadow_tint=None)
    theirs = grade_only("ref", face_above_background=28.8, background_l=None, skin_chroma=29.8,
                        skin_hue=31.9, shadow_tint=7.1)
    rows = rows_by_field(compare(ours, theirs))
    assert all(rows[f].verdict is Verdict.UNSCORED
               for f in ("face_above_background", "background_l", "skin_chroma", "skin_hue", "shadow_tint"))
```

- [ ] **Step 2: Run them to see them fail.** Run `"$PY" -m pytest tests/test_compare.py -q`. Expected: FAIL with `ImportError: cannot import name '_angle'`.

- [ ] **Step 3: Implement.** In `compare.py`, after `_lab_distance`, add:

```python
def _angle(a: Any, b: Any) -> float:
    """Degrees between two hues, the short way round."""
    gap = abs(float(a) - float(b)) % 360.0
    return min(gap, 360.0 - gap)
```

In `TRAITS`, after the `Trait("grade", "lab_mean", ...)` row, add:

```python
    # Per zone (analyze/zones.py). How far the face stands out from the room
    # is most of what makes a reference read as graded.
    Trait("grade", "face_above_background", "face above background", _abs, 6.0, 12.0, "L"),
    Trait("grade", "background_l", "background brightness", _abs, 6.0, 12.0, "L"),
    Trait("grade", "skin_chroma", "skin richness", _abs, 4.0, 8.0, "C"),
    Trait("grade", "skin_hue", "skin hue", _angle, 6.0, 12.0, "°"),
    Trait("grade", "shadow_tint", "shadow tint", _abs, 2.0, 4.0, "a*"),
```

- [ ] **Step 4: Run the tests to see them pass.** Run `"$PY" -m pytest tests/test_compare.py -q`. Expected: 3 passed.

- [ ] **Step 5: Commit.**

```bash
git add packages/pipeline/halfheaven/analyze/compare.py packages/pipeline/tests/test_compare.py
git commit -m "feat(scorecard): score the grade per zone"
```

---

### Task 4: The colourist planner

**Files:**
- Modify: `packages/pipeline/halfheaven/schemas.py`. Add `ZoneControls` and `GradeControls` directly above `class Look`, after the Task 1 models.
- Create: `packages/pipeline/halfheaven/plan/colourist.py`
- Modify: `packages/pipeline/tests/zone_fakes.py`. Add `make_tone` and `make_look`.
- Test: `packages/pipeline/tests/test_colourist.py`

**Interfaces:**
- Consumes: `ZoneLook`, `ZoneTone`, `SkinTone` and `analyze.zones.BAND_CENTRES` (Task 1).
- Produces:
  - `schemas.ZoneControls(curve: list[float] (201), saturation: float, tint_take: list[tuple] (6), tint_ref: list[tuple] (6))`
  - `schemas.GradeControls(strength, white_balance_ab, white_balance_deg, exposure_anchor, subject: ZoneControls, background: ZoneControls, skin_chroma)`
  - `plan.colourist`: `GRID` (201 points from 0 to 100), `tone_curve(take_q, ref_q, anchor) -> list[float]`, `plan_grade(take: ZoneLook, ref: ZoneLook, strength: float) -> GradeControls`, `apply_controls(lab: np.ndarray, controls: GradeControls, zone: "subject" | "background" | "skin") -> np.ndarray`
  - `tests/zone_fakes.py`: `make_tone(center, spread=50.0, chroma=8.0, tint=(0, 0), shadow_a=None)` and `make_look(subject_l=50, background_l=50, skin_l=45, skin_ab=(14, 16), subject_chroma=8, background_chroma=8, background_tint=(0, 0), skin=True)`

- [ ] **Step 1: Add the schema models.** In `schemas.py`, directly above `class Look(BaseModel):`, after `ZoneLook`, add:

```python
class ZoneControls(BaseModel):
    """One zone's grade: a tone curve on L, a saturation scale and a tint shift."""

    # Output L at each point of plan.colourist.GRID (L 0..100 in 201 steps).
    curve: list[float] = Field(min_length=201, max_length=201)
    saturation: float
    # Near-neutral tint per L band of analyze.zones.BANDS: the take's and the reference's.
    tint_take: list[tuple[float, float]] = Field(min_length=6, max_length=6)
    tint_ref: list[tuple[float, float]] = Field(min_length=6, max_length=6)


class GradeControls(BaseModel):
    """A colourist's controls, read from a reference, every one scaled by `strength`."""

    strength: float = Field(ge=0.0, le=1.0)
    # One (a, b) offset for every pixel, aimed by the skin; and the hue turn it makes.
    white_balance_ab: tuple[float, float] = (0.0, 0.0)
    white_balance_deg: float = 0.0
    # The reference's tonal layout is scaled by this so its skin sits where
    # this creator's skin already is.
    exposure_anchor: float = 1.0
    subject: ZoneControls
    background: ZoneControls
    skin_chroma: float = 1.0
```

- [ ] **Step 2: Add the look factories.** Append to `tests/zone_fakes.py`:

```python
from halfheaven.schemas import SkinTone, ZoneLook, ZoneTone


def make_tone(center, spread=50.0, chroma=8.0, tint=(0.0, 0.0), shadow_a=None):
    """A zone whose L runs evenly from center-spread to center+spread, clipped to 0..100."""
    quantiles = np.clip(np.linspace(center - spread, center + spread, 101), 0.0, 100.0)
    return ZoneTone(l_quantiles=[float(v) for v in quantiles], mean_l=float(quantiles.mean()),
                    median_chroma=chroma, tints=[tuple(tint)] * 6, shadow_tint_a=shadow_a)


def make_look(subject_l=50.0, background_l=50.0, skin_l=45.0, skin_ab=(14.0, 16.0),
              subject_chroma=8.0, background_chroma=8.0, background_tint=(0.0, 0.0), skin=True):
    return ZoneLook(
        subject=make_tone(subject_l, chroma=subject_chroma),
        background=make_tone(background_l, chroma=background_chroma, tint=background_tint),
        skin=SkinTone(ab=skin_ab, mean_l=skin_l, median_l=skin_l) if skin else None,
    )
```

- [ ] **Step 3: Write the failing tests.** Create `tests/test_colourist.py`:

```python
"""A colourist's controls, read from a reference: bounded, and gentle with skin."""
import numpy as np
import pytest

from halfheaven.plan.colourist import GRID, apply_controls, plan_grade, tone_curve
from tests.zone_fakes import make_look, make_tone

ZONES = ("subject", "background", "skin")
_rng = np.random.default_rng(7)
PIXELS = np.stack([_rng.uniform(0, 100, 500), _rng.uniform(-40, 40, 500),
                   _rng.uniform(-40, 40, 500)], -1).astype(np.float32)[None]


def test_strength_zero_leaves_every_zone_untouched():
    controls = plan_grade(make_look(background_l=55.0), make_look(background_l=9.0, skin_ab=(25.0, 15.0)), 0.0)
    for zone in ZONES:
        assert np.abs(apply_controls(PIXELS, controls, zone) - PIXELS).max() < 1e-3


def test_matching_looks_barely_move_anything():
    look = make_look(subject_l=45.0, background_l=30.0)
    controls = plan_grade(look, look, 1.0)
    for zone in ("subject", "background"):
        assert np.abs(apply_controls(PIXELS, controls, zone) - PIXELS)[..., 0].mean() < 1.0


@pytest.mark.parametrize("reference", [
    make_tone(0.0, spread=0.0, chroma=0.0),       # a black reference
    make_tone(100.0, spread=0.0, chroma=0.0),     # a white one
    make_tone(9.0),                                # a crushed room, like the day 4 reel's
])
def test_curves_are_monotone_and_slope_limited(reference):
    curve = np.array(tone_curve(make_tone(55.0, spread=40.0).l_quantiles, reference.l_quantiles, 1.0))
    slope = np.diff(curve) / np.diff(GRID)
    assert (slope >= -1e-6).all()
    inside = (curve[:-1] > 0.0) & (curve[1:] < 100.0)
    assert slope[inside].max() <= 1.6 + 1e-6 and slope[inside].min() >= 0.12 - 1e-6


@pytest.mark.parametrize("reference", [
    make_look(subject_l=2.0, background_l=1.0, skin_l=5.0, skin_ab=(0.5, 0.5),
              subject_chroma=0.0, background_chroma=0.0),
    make_look(subject_l=98.0, background_l=99.0, skin_l=95.0, skin_ab=(60.0, -40.0),
              subject_chroma=90.0, background_chroma=90.0),
])
def test_no_reference_pushes_past_the_bounds(reference):
    controls = plan_grade(make_look(), reference, 1.0)
    assert 0.7 <= controls.exposure_anchor <= 1.5
    assert 0.85 <= controls.subject.saturation <= 1.15
    assert 0.8 <= controls.background.saturation <= 1.3
    assert 0.85 <= controls.skin_chroma <= 1.3
    assert abs(controls.white_balance_deg) <= 12.0 * 0.8 + 1e-6


def test_white_balance_turns_skin_only_part_of_the_way():
    take = make_look(skin_ab=(10.0, 17.32))     # hue 60 degrees
    ref = make_look(skin_ab=(-17.32, 10.0))     # hue 150 degrees
    controls = plan_grade(take, ref, 1.0)
    assert controls.white_balance_deg == pytest.approx(9.6, abs=0.01)
    turned = apply_controls(np.array([[[45.0, 10.0, 17.32]]], np.float32), controls, "skin")[0, 0]
    assert np.degrees(np.arctan2(turned[2], turned[1])) == pytest.approx(69.6, abs=1.5)


def test_skin_keeps_its_own_brightness_while_the_room_is_crushed():
    take = make_look(subject_l=55.0, background_l=55.0, skin_l=40.0)
    ref = make_look(subject_l=30.0, background_l=9.0, skin_l=45.0)
    controls = plan_grade(take, ref, 1.0)
    skin = np.array([[[40.0, 14.0, 16.0]]], np.float32)
    wall = np.array([[[55.0, 2.0, 6.0]]], np.float32)
    assert apply_controls(skin, controls, "skin")[0, 0, 0] == pytest.approx(40.0, abs=1e-3)
    assert apply_controls(wall, controls, "background")[0, 0, 0] < 25.0


def test_a_take_with_no_skin_in_view_gets_no_skin_moves():
    controls = plan_grade(make_look(skin=False), make_look(skin_ab=(25.0, 10.0)), 1.0)
    assert controls.white_balance_ab == (0.0, 0.0)
    assert controls.exposure_anchor == 1.0 and controls.skin_chroma == 1.0
    assert np.isfinite(apply_controls(PIXELS, controls, "skin")).all()
```

- [ ] **Step 4: Run them to see them fail.** Run `"$PY" -m pytest tests/test_colourist.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'halfheaven.plan.colourist'`.

- [ ] **Step 5: Implement.** Create `halfheaven/plan/colourist.py`:

```python
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


def tone_curve(take_q: list[float], ref_q: list[float], anchor: float) -> list[float]:
    """Output L on GRID: the take's L quantiles mapped onto the reference's, scaled by `anchor`.

    Beyond the range the take showed, the footage keeps its own contrast
    (slope 1) instead of being flattened: a highlight in a frame that was not
    sampled should not be crushed. Then smoothed, slope-limited, and shifted so
    the take's median still lands where the unlimited curve put it.
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
    median = take[50]
    curve += np.interp(median, GRID, raw) - np.interp(median, GRID, curve)
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


def _zone(zone: str, take: ZoneTone, ref: ZoneTone, anchor: float) -> ZoneControls:
    low, high = SATURATION_RANGE[zone]
    saturation = float(np.clip(ref.median_chroma / max(take.median_chroma, 1e-3), low, high))
    return ZoneControls(curve=tone_curve(take.l_quantiles, ref.l_quantiles, anchor),
                        saturation=saturation, tint_take=list(take.tints), tint_ref=list(ref.tints))


def plan_grade(take: ZoneLook, ref: ZoneLook, strength: float) -> GradeControls:
    """The controls that move `take` toward `ref`, every one within its bounds."""
    white_balance, turn = _white_balance(take.skin, ref.skin)
    anchor = 1.0
    if take.skin is not None and ref.skin is not None and ref.skin.median_l > 1e-3:
        anchor = float(np.clip(take.skin.median_l / ref.skin.median_l, *ANCHOR_RANGE))
    controls = GradeControls(
        strength=strength, white_balance_ab=white_balance, white_balance_deg=turn,
        exposure_anchor=anchor,
        subject=_zone("subject", take.subject, ref.subject, anchor),
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
```

- [ ] **Step 6: Run the tests to see them pass.** Run `"$PY" -m pytest tests/test_colourist.py -q`. Expected: 10 passed.

- [ ] **Step 7: Commit.**

```bash
git add packages/pipeline/halfheaven/schemas.py packages/pipeline/halfheaven/plan/colourist.py \
        packages/pipeline/tests/zone_fakes.py packages/pipeline/tests/test_colourist.py
git commit -m "feat(grade): plan a colourist's bounded controls from two zone looks"
```

---

### Task 5: Baking the zone LUTs

**Files:**
- Modify: `packages/pipeline/halfheaven/render/lut.py`. Extract `_write_cube` from `write_lut`, and add `write_zone_luts`.
- Test: `packages/pipeline/tests/test_lut.py` (append)

**Interfaces:**
- Consumes: `plan.colourist.apply_controls` and `schemas.GradeControls` (Task 4).
- Produces: `render.lut.write_zone_luts(controls: GradeControls, out_dir, size=33) -> dict[str, pathlib.Path]`, with the keys `"subject"`, `"background"` and `"skin"`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_lut.py`:

```python
import cv2
import numpy as np

from halfheaven.plan.colourist import plan_grade
from halfheaven.render.lut import write_zone_luts
from tests.zone_fakes import make_look


def entry(entries, size, r, g, b):
    return np.array(entries[r + g * size + b * size * size], np.float32)


def lightness(rgb):
    return float(cv2.cvtColor(np.array([[rgb]], np.float32), cv2.COLOR_RGB2LAB)[0, 0, 0])


def test_zone_luts_at_zero_strength_are_identities(tmp_path):
    controls = plan_grade(make_look(background_l=55.0), make_look(background_l=9.0), 0.0)
    for zone, path in write_zone_luts(controls, tmp_path, size=17).items():
        size, entries = read_cube(path)
        assert size == 17 and len(entries) == 17 ** 3
        for index in [(3, 5, 7), (8, 8, 8), (15, 10, 5)]:
            expected = np.array(index, np.float32) / (size - 1)
            assert np.abs(entry(entries, size, *index) - expected).max() < 1 / 255, zone


def test_the_skin_lut_keeps_skin_brightness_where_the_subject_lut_darkens(tmp_path):
    controls = plan_grade(make_look(subject_l=55.0, skin_l=40.0), make_look(subject_l=20.0, skin_l=45.0), 1.0)
    paths = write_zone_luts(controls, tmp_path, size=17)
    _, skin = read_cube(paths["skin"])
    _, subject = read_cube(paths["subject"])
    for index in [(10, 7, 5), (12, 9, 8), (6, 4, 3)]:            # skin-like colours
        source = lightness(np.array(index, np.float32) / 16)
        assert lightness(entry(skin, 17, *index)) == pytest.approx(source, abs=1.0)
        assert lightness(entry(subject, 17, *index)) < source - 5
```

- [ ] **Step 2: Run them to see them fail.** Run `"$PY" -m pytest tests/test_lut.py -q`. Expected: FAIL with `ImportError: cannot import name 'write_zone_luts'`.

- [ ] **Step 3: Implement.** In `render/lut.py`, add `from halfheaven.plan.colourist import apply_controls` and `from halfheaven.schemas import GradeControls` to the imports. Replace the body of `write_lut` from `lines = [` onwards with a call to a new shared writer, and add `write_zone_luts`:

```python
def _write_cube(mapped: np.ndarray, size: int, out_path: pathlib.Path, comment: str) -> pathlib.Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# generated by halfheaven - {comment}",
        f"LUT_3D_SIZE {size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
        "",
    ]
    lines += [f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in mapped]
    out_path.write_text("\n".join(lines) + "\n")
    return out_path


def write_lut(
    source: ColorStats,
    target: ColorStats,
    out_path: str | pathlib.Path,
    size: int = DEFAULT_SIZE,
    strength: float = 1.0,
) -> pathlib.Path:
    mapped = transfer(_grid(size), source, target, strength).reshape(-1, 3)
    return _write_cube(mapped, size, pathlib.Path(out_path), "statistical LAB colour transfer")


def write_zone_luts(controls: GradeControls, out_dir: str | pathlib.Path,
                    size: int = DEFAULT_SIZE) -> dict[str, pathlib.Path]:
    """The colourist grade as three .cube files: subject, background and skin."""
    out_dir = pathlib.Path(out_dir)
    lab = cv2.cvtColor(_grid(size), cv2.COLOR_RGB2LAB)
    paths: dict[str, pathlib.Path] = {}
    for zone in ("subject", "background", "skin"):
        graded = apply_controls(lab, controls, zone)
        rgb = np.clip(cv2.cvtColor(graded, cv2.COLOR_LAB2RGB), 0.0, 1.0).reshape(-1, 3)
        paths[zone] = _write_cube(rgb, size, out_dir / f"{zone}.cube", f"colourist grade, {zone}")
    return paths
```

(`_grid` already returns float32 shaped `(N, 1, 3)`, which `cv2.cvtColor` accepts.)

- [ ] **Step 4: Run the tests to see them pass.** Run `"$PY" -m pytest tests/test_lut.py -q`. Expected: all pass, the five existing tests included.

- [ ] **Step 5: Commit.**

```bash
git add packages/pipeline/halfheaven/render/lut.py packages/pipeline/tests/test_lut.py
git commit -m "feat(grade): bake the colourist controls into subject, background and skin LUTs"
```

---

### Task 6: Rendering the zone grade

**Files:**
- Modify: `packages/pipeline/halfheaven/schemas.py`. Add `ZoneGrade` above `class Look` (after `GradeControls`), and `zone_grade` to `Look`.
- Modify: `packages/pipeline/halfheaven/render/video.py`. Add `grade_filters`, restructure the grade and matte section of `build_finish_command` (~lines 259–288), and update `render()` (~lines 432–435).
- Modify: `packages/pipeline/tests/zone_fakes.py`. Add `LeftHalf`, `Nothing`, `identity_lut`, `dark_lut` and `gray`.
- Test: `packages/pipeline/tests/test_render_command.py` (append) and `packages/pipeline/tests/test_zone_grade_render.py` (new)

**Interfaces:**
- Consumes: nothing from earlier tasks at runtime. The tests build LUTs with `write_lut`.
- Produces:
  - `schemas.ZoneGrade(subject_lut: str, background_lut: str, skin_lut: str, skin_weight=0.9, choke_pct=0.005, feather_pct=0.005, controls: GradeControls | None = None)`
  - `Look.zone_grade: ZoneGrade | None`
  - `render.video.grade_filters(grade: ZoneGrade, source: str, subject: str, skin: str, height: int, out: str) -> list[str]`

- [ ] **Step 1: Add the schema.** In `schemas.py`, after `GradeControls`, add:

```python
class ZoneGrade(BaseModel):
    """The colourist grade baked as one LUT per zone, joined through the mattes."""

    subject_lut: str
    background_lut: str
    skin_lut: str
    # Skin takes this share of the skin LUT over the subject/background blend.
    skin_weight: float = Field(default=0.9, ge=0.0, le=1.0)
    # The grade's copy of the subject matte is pulled this far inside the edge,
    # then feathered, both as shares of frame height. Pulling in puts any rim
    # on the hair, where it barely shows, instead of on the wall.
    choke_pct: float = Field(default=0.005, ge=0.0, le=0.05)
    feather_pct: float = Field(default=0.005, ge=0.0, le=0.05)
    # What the LUTs were baked from, for display and later editing.
    controls: GradeControls | None = None
```

In `class Look`, after `background_hex`, add:

```python
    # The colourist grade. Needs a subject and a skin matte for every take;
    # without them the render falls back to `lut`.
    zone_grade: ZoneGrade | None = None
```

- [ ] **Step 2: Extend the stand-ins.** Append to `tests/zone_fakes.py`:

```python
from PIL import Image

from halfheaven.render.lut import ColorStats, write_lut

_NEUTRAL = ColorStats(mean=(50.0, 0.0, 0.0), std=(20.0, 10.0, 10.0))


class LeftHalf:
    def mask_for(self, frame):
        mask = np.zeros(frame.shape[:2], np.uint8)
        mask[:, : frame.shape[1] // 2] = 255
        return mask


class Nothing:
    def mask_for(self, frame):
        return np.zeros(frame.shape[:2], np.uint8)


def identity_lut(path):
    return write_lut(_NEUTRAL, _NEUTRAL, path, size=17)


def dark_lut(path):
    return write_lut(ColorStats(mean=(60.0, 0.0, 0.0), std=(20.0, 10.0, 10.0)),
                     ColorStats(mean=(25.0, 0.0, 0.0), std=(12.0, 10.0, 10.0)), path, size=17)


def gray(image_or_path):
    image = image_or_path if isinstance(image_or_path, Image.Image) else Image.open(image_or_path)
    return np.array(image.convert("L")).astype(int)
```

- [ ] **Step 3: Write the failing command tests.** Append to `tests/test_render_command.py`:

```python
from halfheaven.schemas import ZoneGrade


def zone_look(tmp_path, **extra):
    luts = {}
    for name in ("s", "b", "k"):
        path = tmp_path / f"{name}.cube"
        path.write_text("LUT_3D_SIZE 2\n")
        luts[name] = str(path)
    grade = ZoneGrade(subject_lut=luts["s"], background_lut=luts["b"], skin_lut=luts["k"])
    return Look(lut=luts["b"], zone_grade=grade, **extra)


def test_the_colourist_grade_runs_three_luts_through_the_mattes(tmp_path):
    subject, skin = tmp_path / "subject.mp4", tmp_path / "skin.mp4"
    command = build_finish_command(program(look=zone_look(tmp_path)), tmp_path / "b.mp4",
                                   tmp_path / "o.mp4", tmp_path, subject_track=subject, skin_track=skin)
    graph = graph_of(command)
    assert graph.count("lut3d") == 3
    assert "erosion" in graph and graph.count("alphamerge") == 2
    assert command.count(str(subject)) == 1 and command.count(str(skin)) == 1


def test_without_mattes_the_colourist_grade_falls_back_to_one_lut(tmp_path):
    command = build_finish_command(program(look=zone_look(tmp_path)), tmp_path / "b.mp4",
                                   tmp_path / "o.mp4", tmp_path)
    assert graph_of(command).count("lut3d") == 1


def test_the_subject_matte_is_read_once_for_grade_captions_and_backdrop(tmp_path):
    subject, skin = tmp_path / "subject.mp4", tmp_path / "skin.mp4"
    look = zone_look(tmp_path, background_hex="#112233", letterbox_top_pct=0.1, letterbox_bottom_pct=0.1)
    edit = program(captions=2, look=look)
    edit = edit.model_copy(update={"captions": [c.model_copy(update={"behind": True}) for c in edit.captions]})
    command = build_finish_command(edit, tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path,
                                   subject_track=subject, skin_track=skin)
    graph = graph_of(command)
    assert command.count(str(subject)) == 1
    assert "split=3[matte0][matte1][matte2]" in graph
    assert graph.index("lut3d") < graph.index("pad=")      # graded before the letterbox
```

- [ ] **Step 4: Write the failing render tests.** Create `tests/test_zone_grade_render.py`:

```python
"""The colourist grade, rendered: each zone takes its own LUT."""
import pytest

from halfheaven.analyze.segment import write_matte_video
from halfheaven.render.video import extract_frame, render
from halfheaven.schemas import Canvas, EditProgram, Look, TakeMatte, VideoClip, ZoneGrade
from tests.zone_fakes import BARS, LeftHalf, Nothing, dark_lut, gray, identity_lut

BASE = dict(canvas=Canvas(width=320, height=568, fps=30),
            video=[VideoClip(src=str(BARS), start=0.0, end=2.0)])


def halves(program, tmp_path, name):
    out = render(program, tmp_path / f"{name}.mp4", work_dir=tmp_path / name)
    frame = gray(extract_frame(out, 1.0, tmp_path / f"{name}.png"))
    return frame[:, 20:140].mean(), frame[:, 180:300].mean()


def mattes(tmp_path, skin_segmenter):
    left = write_matte_video(BARS, LeftHalf(), tmp_path / "left.mp4", feather=0)
    skin = write_matte_video(BARS, skin_segmenter, tmp_path / "skin.mp4", feather=0)
    return {str(BARS): TakeMatte(subject=str(left), skin=str(skin))}


def test_the_background_takes_its_own_grade_and_the_subject_keeps_its_own(tmp_path):
    grade = ZoneGrade(subject_lut=str(identity_lut(tmp_path / "i.cube")),
                      background_lut=str(dark_lut(tmp_path / "d.cube")),
                      skin_lut=str(identity_lut(tmp_path / "k.cube")))
    plain = halves(EditProgram(**BASE), tmp_path, "plain")
    zoned = halves(EditProgram(**BASE, look=Look(zone_grade=grade, mattes=mattes(tmp_path, Nothing()))),
                   tmp_path, "zoned")
    assert zoned[0] == pytest.approx(plain[0], abs=4), "the subject's LUT is the identity"
    assert zoned[1] < plain[1] - 10, "the background's LUT darkens"


def test_skin_keeps_its_brightness_when_the_subject_is_darkened(tmp_path):
    grade = ZoneGrade(subject_lut=str(dark_lut(tmp_path / "d.cube")),
                      background_lut=str(identity_lut(tmp_path / "i.cube")),
                      skin_lut=str(identity_lut(tmp_path / "k.cube")))
    plain = halves(EditProgram(**BASE), tmp_path, "plain")
    zoned = halves(EditProgram(**BASE, look=Look(zone_grade=grade, mattes=mattes(tmp_path, LeftHalf()))),
                   tmp_path, "zoned")
    assert zoned[0] == pytest.approx(plain[0], abs=10), "skin takes 90% of its own (identity) LUT"
    assert zoned[1] == pytest.approx(plain[1], abs=4)


def test_a_missing_matte_falls_back_to_the_single_lut(tmp_path):
    grade = ZoneGrade(subject_lut=str(identity_lut(tmp_path / "i.cube")),
                      background_lut=str(identity_lut(tmp_path / "i2.cube")),
                      skin_lut=str(identity_lut(tmp_path / "k.cube")))
    gone = {str(BARS): TakeMatte(subject=str(tmp_path / "gone.mp4"), skin=str(tmp_path / "gone.mp4"))}
    look = Look(lut=str(dark_lut(tmp_path / "d.cube")), zone_grade=grade, mattes=gone)
    plain = halves(EditProgram(**BASE), tmp_path, "plain")
    fallback = halves(EditProgram(**BASE, look=look), tmp_path, "fallback")
    assert fallback[0] < plain[0] - 10 and fallback[1] < plain[1] - 10
```

- [ ] **Step 5: Run them to see them fail.** Run `"$PY" -m pytest tests/test_render_command.py tests/test_zone_grade_render.py -q`. Expected: the new tests FAIL. The command tests find one `lut3d` instead of three, and the render tests fail their brightness assertions.

- [ ] **Step 6: Implement `grade_filters`.** In `render/video.py`, change `from halfheaven.schemas import Canvas, EditProgram, VideoClip` to also import `ZoneGrade`. Add above `build_finish_command`:

```python
def grade_filters(grade: ZoneGrade, source: str, subject: str, skin: str, height: int,
                  out: str) -> list[str]:
    """The colourist grade as filtergraph steps: `source` graded into `out`.

    Three LUTs run side by side. The subject's is laid over the background's
    through a copy of the subject matte pulled inside the edge and feathered,
    then the skin's over that through the skin matte. `subject` and `skin` are
    matte streams on the same frame grid as `source`; `height` is its height.
    """
    def lut(path: str) -> str:
        return f"lut3d=file='{path}':interp=tetrahedral"

    # `erosion` shrinks a matte by one pixel per pass.
    choke = ["erosion"] * max(0, round(grade.choke_pct * height))
    sigma = grade.feather_pct * height
    feather = [f"gblur=sigma={sigma:.2f}"] if sigma > 0 else []
    matte = ",".join(["format=gray", *choke, *feather])
    return [
        f"{source}split=3[zs][zb][zk]",
        f"[zb]{lut(grade.background_lut)}[zbg]",
        f"[zs]{lut(grade.subject_lut)},format=yuva420p[zsg]",
        f"{subject}{matte}[zsm]",
        "[zsg][zsm]alphamerge[zsa]",
        "[zbg][zsa]overlay=0:0[zz]",
        f"[zk]{lut(grade.skin_lut)},format=yuva420p[zkg]",
        f"{skin}format=gray,lut=c0='val*{grade.skin_weight:.3f}'[zkm]",
        "[zkg][zkm]alphamerge[zka]",
        f"[zz][zka]overlay=0:0{out}",
    ]
```

- [ ] **Step 7: Restructure the grade in `build_finish_command`.** Replace everything from `if look.lut:` through the end of the `if behind or replace:` block (the `mattes = [matte]` line) with:

```python
    subject = subject_track or look.matte
    # The colourist grade needs both mattes. Without either it falls back to
    # the single LUT below, rather than grading some zones and not others.
    zoned = look.zone_grade is not None and subject is not None and skin_track is not None
    behind = subject is not None and any(c.behind for c in program.captions)
    replace = subject is not None and look.background_hex is not None
    mattes: list[str] = []
    uses = int(zoned) + int(behind) + int(replace)
    if uses:
        # One read of the matte, split between the uses that need it.
        matte = add_input("-i", str(subject))
        if uses > 1:
            steps.append(f"{matte}split={uses}" + "".join(f"[matte{k}]" for k in range(uses)))
            mattes = [f"[matte{k}]" for k in range(uses)]
        else:
            mattes = [matte]

    # Grade before letterboxing so the bars stay pure black, and before the
    # captions so they keep the exact colour the profile asked for.
    if zoned:
        skin = add_input("-i", str(skin_track))
        steps += grade_filters(look.zone_grade, label, mattes.pop(0), skin, height, "[vg]")
        label = "[vg]"
    elif look.lut:
        lut = f"lut3d=file='{look.lut}':interp=tetrahedral"
        if skin_track and look.skin_protect > 0:
            # The graded picture is laid over the ungraded one with the skin
            # matte as its (inverted) alpha: everything takes the full grade,
            # skin takes `1 - skin_protect` of it.
            skin = add_input("-i", str(skin_track))
            steps.append(f"{label}split=2[ungraded][tograde]")
            steps.append(f"[tograde]{lut},format=yuva420p[graded]")
            steps.append(f"{skin}format=gray,lut=c0='255-val*{look.skin_protect:.3f}'[gradeweight]")
            steps.append("[graded][gradeweight]alphamerge[gradedskin]")
            steps.append("[ungraded][gradedskin]overlay=0:0[vg]")
        else:
            steps.append(f"{label}{lut}[vg]")
        label = "[vg]"
```

The `if replace:` and `if behind:` blocks that follow keep their `mattes.pop(0)` calls unchanged.

- [ ] **Step 8: Build the tracks in `render()`.** Replace:

```python
    needs_subject = look.background_hex is not None or any(c.behind for c in program.captions)
    subject = mask_track(program, "subject", work_dir) if needs_subject else None
    skin = mask_track(program, "skin", work_dir) if look.lut and look.skin_protect > 0 else None
```

with:

```python
    zoned = look.zone_grade is not None
    needs_subject = zoned or look.background_hex is not None or any(c.behind for c in program.captions)
    subject = mask_track(program, "subject", work_dir) if needs_subject else None
    wants_skin = zoned or (look.lut is not None and look.skin_protect > 0)
    skin = mask_track(program, "skin", work_dir) if wants_skin else None
```

- [ ] **Step 9: Run the tests to see them pass.** Run `"$PY" -m pytest tests/test_render_command.py tests/test_zone_grade_render.py tests/test_subject_mattes.py tests/test_render.py -q`. Expected: all pass. This includes the existing `test_skin_keeps_more_of_its_own_colour_under_a_grade`, which checks the fallback path is unchanged.

- [ ] **Step 10: Commit.**

```bash
git add packages/pipeline/halfheaven/schemas.py packages/pipeline/halfheaven/render/video.py \
        packages/pipeline/tests/zone_fakes.py packages/pipeline/tests/test_render_command.py \
        packages/pipeline/tests/test_zone_grade_render.py
git commit -m "feat(grade): render the colourist grade through the subject and skin mattes"
```

---

### Task 7: Previews show the zone grade

**Files:**
- Modify: `packages/pipeline/halfheaven/previews.py`. Change `background()` (~line 83) and its one call in `render_previews` (~line 118).
- Test: `packages/pipeline/tests/test_zone_grade_render.py` (append)

**Interfaces:**
- Consumes: `render.video.grade_filters` and `render.video.mask_track` (Task 6).
- Produces: `previews.background(video, at, look: Look, out, subject=None, skin=None, height=None) -> PIL.Image`. The third argument changed from a LUT path to the `Look`.

- [ ] **Step 1: Write the failing test.** Append to `tests/test_zone_grade_render.py`:

```python
from halfheaven.previews import background


def test_a_preview_is_graded_the_way_the_render_is(tmp_path):
    grade = ZoneGrade(subject_lut=str(identity_lut(tmp_path / "i.cube")),
                      background_lut=str(dark_lut(tmp_path / "d.cube")),
                      skin_lut=str(identity_lut(tmp_path / "k.cube")))
    left = write_matte_video(BARS, LeftHalf(), tmp_path / "left.mp4", feather=0)
    nothing = write_matte_video(BARS, Nothing(), tmp_path / "none.mp4", feather=0)
    plain = gray(background(BARS, 1.0, Look(), tmp_path / "plain.png"))
    graded = gray(background(BARS, 1.0, Look(zone_grade=grade), tmp_path / "graded.png",
                             subject=left, skin=nothing, height=568))
    assert graded[:, 20:140].mean() == pytest.approx(plain[:, 20:140].mean(), abs=4)
    assert graded[:, 180:300].mean() < plain[:, 180:300].mean() - 10
```

- [ ] **Step 2: Run it to see it fail.** Run `"$PY" -m pytest tests/test_zone_grade_render.py::test_a_preview_is_graded_the_way_the_render_is -q`. Expected: FAIL. `background()` has no `subject` parameter, and it treats a `Look` as a path.

- [ ] **Step 3: Implement.** In `previews.py`, add these imports:

```python
from halfheaven.media.probe import probe
from halfheaven.render.video import grade_filters, mask_track
```

Change `from halfheaven.schemas import Caption, EditProgram, StyleProfile` to also import `Look`. Replace `background` with:

```python
def background(video: pathlib.Path, at: float, look: Look, out: pathlib.Path,
               subject: pathlib.Path | None = None, skin: pathlib.Path | None = None,
               height: int | None = None) -> Image.Image:
    """The edit's picture at `at`, graded as the finished render grades it."""
    seek = ["-ss", f"{max(0.0, at):.3f}"]
    if look.zone_grade is not None and subject is not None and skin is not None:
        frame_height = height or probe(video).height
        graph = ";".join(grade_filters(look.zone_grade, "[0:v]", "[1:v]", "[2:v]",
                                       frame_height, "[graded]"))
        command = [ffmpeg(), "-v", "error", "-y", *seek, "-i", str(video), *seek, "-i", str(subject),
                   *seek, "-i", str(skin), "-filter_complex", graph, "-map", "[graded]",
                   "-frames:v", "1", str(out)]
    else:
        graded = (["-vf", f"lut3d=file='{look.lut}':interp=tetrahedral"]
                  if look.lut and pathlib.Path(look.lut).exists() else [])
        command = [ffmpeg(), "-v", "error", "-y", *seek, "-i", str(video), *graded,
                   "-frames:v", "1", str(out)]
    subprocess.run(command, check=True, capture_output=True)
    return Image.open(out).convert("RGBA")
```

In `render_previews`, replace `picture = background(base, at, program.look.lut, scratch_dir / "frame.png")` with:

```python
        # The render left its mattes on the program timeline in `work`;
        # mask_track reuses them rather than cutting them again.
        zoned = program.look.zone_grade is not None
        subject = mask_track(program, "subject", work) if zoned else None
        skin = mask_track(program, "skin", work) if zoned else None
        picture = background(base, at, program.look, scratch_dir / "frame.png",
                             subject, skin, canvas.height)
```

- [ ] **Step 4: Run the tests to see them pass.** Run `"$PY" -m pytest tests/test_zone_grade_render.py tests/test_studio_outputs.py -q`. Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git add packages/pipeline/halfheaven/previews.py packages/pipeline/tests/test_zone_grade_render.py
git commit -m "feat(grade): caption-look previews show the colourist grade"
```

---

### Task 8: Choosing the grade in the pipeline

**Files:**
- Create: `packages/pipeline/halfheaven/plan/grade.py`
- Modify: `packages/pipeline/halfheaven/cli.py`. Change the grade block (~lines 217–243) and the imports (~lines 30–32).
- Test: `packages/pipeline/tests/test_grade_wiring.py`

**Interfaces:**
- Consumes: `take_zone_look` (Task 1), `plan_grade` (Task 4), `write_zone_luts` (Task 5), `ZoneGrade` (Task 6).
- Produces: `plan.grade.global_lut_for(profile, takes, work) -> tuple[pathlib.Path, ColorStats] | None`, `plan.grade.zone_grade_for(profile, takes, mattes, work) -> ZoneGrade | None` and `plan.grade.describe_controls(controls) -> str`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_grade_wiring.py`:

```python
"""Which grade a render gets, and what it is baked from."""
import pathlib

from halfheaven.analyze.segment import write_matte_video
from halfheaven.plan.grade import describe_controls, global_lut_for, zone_grade_for
from halfheaven.schemas import GradeProfile, StyleProfile, TakeMatte
from tests.zone_fakes import WIDE, Bright, make_look


def zoned_profile(**grade):
    return StyleProfile(grade=GradeProfile(measured=True, zones=make_look(background_l=40.0), **grade))


def ellipse_mattes(tmp_path, skin=True):
    matte = write_matte_video(WIDE, Bright(), tmp_path / "m.mp4", feather=0)
    return {str(WIDE): TakeMatte(subject=str(matte), skin=str(matte) if skin else None)}


def test_the_colourist_grade_is_made_when_everything_is_there(tmp_path):
    profile = zoned_profile()
    grade = zone_grade_for(profile, [str(WIDE)], ellipse_mattes(tmp_path), tmp_path)
    assert grade is not None
    assert all(pathlib.Path(p).exists() for p in (grade.subject_lut, grade.background_lut, grade.skin_lut))
    assert grade.controls.strength == profile.grade.strength
    assert "white balance" in describe_controls(grade.controls)


def test_no_zones_means_no_colourist_grade(tmp_path):
    profile = StyleProfile(grade=GradeProfile(measured=True))
    assert zone_grade_for(profile, [str(WIDE)], ellipse_mattes(tmp_path), tmp_path) is None


def test_a_take_without_a_skin_matte_keeps_the_single_grade(tmp_path):
    assert zone_grade_for(zoned_profile(), [str(WIDE)], ellipse_mattes(tmp_path, skin=False), tmp_path) is None


def test_the_single_lut_is_baked_only_for_a_measured_reference(tmp_path):
    baked = global_lut_for(StyleProfile(grade=GradeProfile(measured=True)), [str(WIDE)], tmp_path)
    assert baked is not None and baked[0].exists()
    assert global_lut_for(StyleProfile(), [str(WIDE)], tmp_path) is None
```

- [ ] **Step 2: Run them to see them fail.** Run `"$PY" -m pytest tests/test_grade_wiring.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'halfheaven.plan.grade'`.

- [ ] **Step 3: Implement.** Create `halfheaven/plan/grade.py`:

```python
"""Choosing and baking the grade for a set of takes.

Two grades exist. The colourist grade (plan/colourist.py) needs the
reference's zones and a subject and skin matte for every take. The single
statistical LUT is what runs when it cannot be made, and it is always baked,
so a render that loses a matte still has a grade to fall back to.
"""
from __future__ import annotations

import pathlib

from halfheaven.analyze.framing import detect_letterbox
from halfheaven.analyze.grade import measure_color_stats
from halfheaven.analyze.zones import take_zone_look
from halfheaven.plan.colourist import plan_grade
from halfheaven.render.lut import ColorStats, write_lut, write_zone_luts
from halfheaven.schemas import GradeControls, StyleProfile, TakeMatte, ZoneGrade


def global_lut_for(profile: StyleProfile, takes: list[str],
                   work: str | pathlib.Path) -> tuple[pathlib.Path, ColorStats] | None:
    """The single LUT, from the first take's colour to the reference's, and the take's stats.

    Measured from the first take: several takes of one setup share a look.
    Strength is a dial because pushing bright footage all the way to a dark
    reference turns it muddy.
    """
    if not profile.grade.measured:
        return None
    primary = takes[0]
    source = measure_color_stats(primary, framing=detect_letterbox(primary))
    lut = write_lut(source=source,
                    target=ColorStats(mean=profile.grade.lab_mean, std=profile.grade.lab_std),
                    out_path=pathlib.Path(work) / "grade.cube", strength=profile.grade.strength)
    return lut, source


def zone_grade_for(profile: StyleProfile, takes: list[str], mattes: dict[str, TakeMatte],
                   work: str | pathlib.Path) -> ZoneGrade | None:
    """The colourist grade for these takes, or None when it cannot be made.

    None when the reference showed no readable person, or when any take lacks
    a subject or skin matte. The caller then keeps the single LUT.
    """
    reference = profile.grade.zones
    if reference is None or any(take not in mattes or not mattes[take].skin for take in takes):
        return None
    take = take_zone_look(takes, mattes)
    if take is None:
        return None
    controls = plan_grade(take, reference, profile.grade.strength)
    luts = write_zone_luts(controls, pathlib.Path(work) / "grade")
    return ZoneGrade(subject_lut=str(luts["subject"]), background_lut=str(luts["background"]),
                     skin_lut=str(luts["skin"]), controls=controls)


def describe_controls(controls: GradeControls) -> str:
    return (f"white balance {controls.white_balance_deg:+.1f}°, "
            f"exposure anchor x{controls.exposure_anchor:.2f}, "
            f"saturation subject x{controls.subject.saturation:.2f} "
            f"background x{controls.background.saturation:.2f}, "
            f"skin richness x{controls.skin_chroma:.2f}, strength {controls.strength:.2f}")
```

- [ ] **Step 4: Wire it into `cli.py`.** Replace the whole block from `if profile.grade.measured:` (the one under `look = Look(...)`, ~line 217) through the `else: print(f"      no subject separation: {matting.reason}")` lines with:

```python
    baked = global_lut_for(profile, takes, work)
    if baked is not None:
        lut, take_stats = baked
        look = look.model_copy(update={"lut": str(lut)})
        print(f"      grade: target LAB mean={tuple(round(v, 1) for v in take_stats.mean)} "
              f"-> reference, strength {profile.grade.strength}")
    mattes = matting.result()
    if mattes:
        print(f"      subject separated in {matting.seconds:.0f}s "
              f"(the edit waited {matting.waited:.0f}s for it)")
        look = look.model_copy(update={
            "mattes": mattes,
            "skin_protect": profile.subject.skin_protect if look.lut else 0.0,
            "background_hex": profile.subject.background_hex,
        })
        zone_grade = zone_grade_for(profile, takes, mattes, work)
        if zone_grade is not None:
            look = look.model_copy(update={"zone_grade": zone_grade})
            print(f"      colourist grade: {describe_controls(zone_grade.controls)}")
        elif profile.grade.zones is None:
            print("      colourist grade: no person read in the reference, keeping the single grade")
    else:
        print(f"      no subject separation: {matting.reason}")
```

Add `from halfheaven.plan.grade import describe_controls, global_lut_for, zone_grade_for` to the imports. Then run `grep -n "detect_letterbox\|measure_color_stats\|write_lut\|ColorStats" packages/pipeline/halfheaven/cli.py` and delete each of those four imports that no longer has a use.

- [ ] **Step 5: Run the tests.** Run `"$PY" -m pytest tests/test_grade_wiring.py -q && "$PY" -c "import halfheaven.cli"`. Expected: 4 passed, and the import succeeds.

- [ ] **Step 6: Commit.**

```bash
git add packages/pipeline/halfheaven/plan/grade.py packages/pipeline/halfheaven/cli.py \
        packages/pipeline/tests/test_grade_wiring.py
git commit -m "feat(grade): the pipeline makes the colourist grade when it can"
```

---

### Task 9: Seam and flicker metrics

**Files:**
- Create: `packages/pipeline/halfheaven/analyze/grade_eval.py` (metrics only in this task)
- Test: `packages/pipeline/tests/test_grade_eval.py`

**Interfaces:**
- Produces: `grade_eval.seam(lightness, alpha) -> float | None`, `grade_eval.flicker(frames, raw_frames, alphas, skins) -> dict[str, float | None]` (keys `room` and `face`), and the constants `SEAM_LIMIT = 2.0`, `FLICKER_LIMIT = 1.0` and `FACE_LIMIT = 2.0`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_grade_eval.py`:

```python
"""Measuring what a grade does at the matte edge and over time."""
import numpy as np
import pytest

from halfheaven.analyze.grade_eval import flicker, seam


def edge_scene():
    lightness = np.full((568, 100), 20.0, np.float32)
    lightness[:, :50] = 60.0
    alpha = np.zeros((568, 100), np.float32)
    alpha[:, :50] = 1.0
    return lightness, alpha


def test_a_clean_edge_has_no_seam():
    lightness, alpha = edge_scene()
    assert seam(lightness, alpha) == pytest.approx(0.0, abs=0.5)


def test_a_bright_rim_reads_positive_and_a_dark_line_negative():
    lightness, alpha = edge_scene()
    rim, line = lightness.copy(), lightness.copy()
    rim[:, 50:52] = 90.0         # just outside the subject: a glow on the wall
    line[:, 48:50] = 0.0         # just inside: a dark outline on the hair
    assert seam(rim, alpha) > 3.0
    assert seam(line, alpha) < -3.0


def test_flicker_is_what_the_grade_adds_over_the_footage():
    raw = [np.full((60, 60), 30.0, np.float32) for _ in range(6)]
    steady = [frame.copy() for frame in raw]
    pumping = [frame + (3.0 if k % 2 else 0.0) for k, frame in enumerate(raw)]
    alphas = [np.zeros((60, 60), np.float32)] * 6
    skins = [np.zeros((60, 60), np.float32)] * 6
    assert flicker(steady, raw, alphas, skins)["room"] == pytest.approx(0.0)
    assert flicker(pumping, raw, alphas, skins)["room"] == pytest.approx(3.0)
    assert flicker(steady, raw, alphas, skins)["face"] is None
```

- [ ] **Step 2: Run them to see them fail.** Run `"$PY" -m pytest tests/test_grade_eval.py -q`. Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement.** Create `halfheaven/analyze/grade_eval.py` with the metrics. Task 10 adds the runner to the same file.

```python
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
```

- [ ] **Step 4: Run the tests to see them pass.** Run `"$PY" -m pytest tests/test_grade_eval.py -q`. Expected: 3 passed.

- [ ] **Step 5: Commit.**

```bash
git add packages/pipeline/halfheaven/analyze/grade_eval.py packages/pipeline/tests/test_grade_eval.py
git commit -m "feat(grade): seam and flicker metrics for the zone grade"
```

---

### Task 10: The evaluation runner

**Files:**
- Modify: `packages/pipeline/halfheaven/analyze/grade_eval.py` (append the runner)
- Test: `packages/pipeline/tests/test_grade_eval.py` (append)

**Interfaces:**
- Consumes: `global_lut_for`, `zone_grade_for` (Task 8); `take_zone_look`, `summarise`, `shrink`, `to_lab` (Task 1); `render` (Task 6); `apply_fingerprint` (Task 2); `matte_takes`; `extract_fingerprint`.
- Produces:
  - `grade_eval.evaluate_pair(take: str, matte: TakeMatte, reference: dict, out_dir, strength=None, choke_pct=None, feather_pct=None) -> dict`. The report has keys `take`, `reference`, `reference_summary`, `raw`, `today`, plus `colourist` when made, plus `controls`.
  - `grade_eval.verdict(reports: list[dict]) -> dict`
  - `grade_eval.main(argv)` runs as `python -m halfheaven.analyze.grade_eval`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_grade_eval.py`:

```python
from halfheaven.analyze.grade_eval import evaluate_pair, verdict
from halfheaven.analyze.segment import write_matte_video
from halfheaven.analyze.zones import summarise
from halfheaven.schemas import TakeMatte
from tests.zone_fakes import WIDE, Bright, make_look


def fake_fingerprint():
    look = make_look(subject_l=60.0, background_l=40.0, skin_l=70.0, skin_ab=(12.0, 18.0))
    reading = lambda value: {"value": value, "confidence": "measured", "note": ""}
    return {"source": "fake.mp4",
            "grade": {"lab_mean": reading([35.0, 6.0, 4.0]), "lab_std": reading([15.0, 8.0, 9.0]),
                      **{name: reading(value) for name, value in summarise(look).items()}},
            "zone_look": look.model_dump()}


def test_a_pair_is_rendered_both_ways_and_measured(tmp_path):
    matte = write_matte_video(WIDE, Bright(), tmp_path / "m.mp4", feather=0)
    report = evaluate_pair(str(WIDE), TakeMatte(subject=str(matte), skin=str(matte)),
                           fake_fingerprint(), tmp_path / "pair")
    assert (tmp_path / "pair" / "today.mp4").exists() and (tmp_path / "pair" / "colourist.mp4").exists()
    assert report["colourist"]["background_l"] > report["raw"]["background_l"] + 5
    assert {"seam", "flicker_room", "flicker_face", "face_l_change", "render_seconds"} <= set(report["colourist"])
    assert verdict([report])["fallback_pairs"] == []


def test_a_reference_without_zones_is_scored_as_a_fallback(tmp_path):
    matte = write_matte_video(WIDE, Bright(), tmp_path / "m.mp4", feather=0)
    fingerprint = fake_fingerprint()
    fingerprint.pop("zone_look")
    report = evaluate_pair(str(WIDE), TakeMatte(subject=str(matte), skin=str(matte)), fingerprint, tmp_path / "pair")
    assert "colourist" not in report and "today" in report
    assert verdict([report])["fallback_pairs"] == [f"{WIDE} x fake.mp4"]
```

- [ ] **Step 2: Run them to see them fail.** Run `"$PY" -m pytest tests/test_grade_eval.py -q`. Expected: the two new tests FAIL with `ImportError: cannot import name 'evaluate_pair'`.

- [ ] **Step 3: Implement.** Add these imports to the top of `grade_eval.py`, below `import numpy as np`:

```python
import argparse
import json
import pathlib
import time

from halfheaven.analyze.fingerprint import extract_fingerprint
from halfheaven.analyze.matte import matte_takes
from halfheaven.analyze.zones import shrink, summarise, take_zone_look, to_lab
from halfheaven.media.probe import probe
from halfheaven.plan.grade import global_lut_for, zone_grade_for
from halfheaven.plan.typography import apply_fingerprint
from halfheaven.render.video import extract_frame, render
from halfheaven.schemas import Canvas, EditProgram, Look, StyleProfile, TakeMatte, VideoClip
```

Then append:

```python
ZONE_TRAITS = ("face_above_background", "background_l", "skin_chroma", "skin_hue", "shadow_tint")
SEAM_FRAMES = 8
FLICKER_STARTS = (0.2, 0.5, 0.8)
FLICKER_RUN = 8


def _frame_count(path: str | pathlib.Path) -> int:
    capture = cv2.VideoCapture(str(path))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    return count


def _read(path: str | pathlib.Path, indices: list[int]) -> list[np.ndarray | None]:
    capture = cv2.VideoCapture(str(path))
    frames: list[np.ndarray | None] = []
    try:
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            frames.append(frame if ok else None)
    finally:
        capture.release()
    return frames


def _lightness(path, indices) -> list[np.ndarray | None]:
    return [None if f is None else to_lab(shrink(f))[..., 0] for f in _read(path, indices)]


def _weights(path, indices, shape) -> list[np.ndarray | None]:
    return [None if f is None else
            cv2.resize(f[..., 0], (shape[1], shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
            for f in _read(path, indices)]


def _mean(values: list[float]) -> float | None:
    return round(float(np.mean(values)), 2) if values else None


def edge_and_flicker(take: str, output: pathlib.Path, matte: TakeMatte) -> dict[str, float | None]:
    """The output's seam and flicker, each measured relative to the raw take's own."""
    total = min(_frame_count(take), _frame_count(output))
    picks = [int(total * (i + 0.5) / SEAM_FRAMES) for i in range(SEAM_FRAMES)]
    raw, out = _lightness(take, picks), _lightness(output, picks)
    shape = next((f.shape for f in raw if f is not None), None)
    gaps: list[float] = []
    if shape is not None:
        for r, o, alpha in zip(raw, out, _weights(matte.subject, picks, shape)):
            if r is None or o is None or alpha is None:
                continue
            before, after = seam(r, alpha), seam(o, alpha)
            if before is not None and after is not None:
                gaps.append(after - before)
    room: list[float] = []
    face: list[float] = []
    for share in FLICKER_STARTS:
        start = int(total * share)
        run = list(range(start, min(total, start + FLICKER_RUN)))
        raw_run, out_run = _lightness(take, run), _lightness(output, run)
        if len(run) < 2 or any(f is None for f in raw_run + out_run):
            continue
        size = raw_run[0].shape
        alphas = _weights(matte.subject, run, size)
        skins = (_weights(matte.skin, run, size) if matte.skin
                 else [np.zeros(size, np.float32)] * len(run))
        if any(a is None for a in alphas + skins):
            continue
        result = flicker(out_run, raw_run, alphas, skins)
        if result["room"] is not None:
            room.append(result["room"])
        if result["face"] is not None:
            face.append(result["face"])
    return {"seam": _mean(gaps), "flicker_room": _mean(room), "flicker_face": _mean(face)}


def _reference_summary(fingerprint: dict) -> dict[str, float | None]:
    grade = fingerprint.get("grade") or {}
    return {name: (grade.get(name) or {}).get("value") for name in ZONE_TRAITS}


def _stills(video: str | pathlib.Path, prefix: pathlib.Path) -> None:
    duration = probe(video).duration
    for label, share in (("a", 1 / 3), ("b", 2 / 3)):
        extract_frame(video, duration * share, prefix.with_name(f"{prefix.name}_{label}.jpg"))


def evaluate_pair(take: str, matte: TakeMatte, reference: dict, out_dir: str | pathlib.Path,
                  strength: float | None = None, choke_pct: float | None = None,
                  feather_pct: float | None = None) -> dict:
    """Render `take` with today's grade and the colourist grade toward `reference`, and measure both."""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = apply_fingerprint(StyleProfile(), reference)
    if strength is not None:
        profile = profile.model_copy(update={"grade": profile.grade.model_copy(update={"strength": strength})})
    info = probe(take)
    canvas = Canvas(width=info.width // 2 * 2, height=info.height // 2 * 2, fps=info.fps)
    clip = VideoClip(src=take, start=0.0, end=info.duration)
    mattes = {take: matte}
    today = Look(mattes=mattes, skin_protect=profile.subject.skin_protect)
    baked = global_lut_for(profile, [take], out_dir)
    if baked is not None:
        today = today.model_copy(update={"lut": str(baked[0])})
    zone = zone_grade_for(profile, [take], mattes, out_dir)
    if zone is not None and (choke_pct is not None or feather_pct is not None):
        zone = zone.model_copy(update={k: v for k, v in (("choke_pct", choke_pct), ("feather_pct", feather_pct))
                                       if v is not None})
    raw_look = take_zone_look([take], mattes)
    report: dict = {"take": take, "reference": reference.get("source"),
                    "reference_summary": _reference_summary(reference), "raw": summarise(raw_look),
                    "controls": zone.controls.model_dump() if zone and zone.controls else None}
    _stills(take, out_dir / "raw")
    variants = {"today": today}
    if zone is not None:
        variants["colourist"] = today.model_copy(update={"zone_grade": zone})
    for name, look in variants.items():
        path = out_dir / f"{name}.mp4"
        started = time.monotonic()
        render(EditProgram(canvas=canvas, video=[clip], look=look), path, out_dir / f"work_{name}")
        seconds = time.monotonic() - started
        graded = take_zone_look([str(path)], {str(path): matte})
        face = (None if not (graded and graded.skin and raw_look and raw_look.skin)
                else round(graded.skin.median_l - raw_look.skin.median_l, 2))
        report[name] = {**summarise(graded), "face_l_change": face, "render_seconds": round(seconds, 1),
                        **edge_and_flicker(take, path, matte)}
        _stills(path, out_dir / name)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    return report


def _distance(trait: str, ours: float, theirs: float) -> float:
    if trait == "skin_hue":
        gap = abs(ours - theirs) % 360.0
        return min(gap, 360.0 - gap)
    return abs(ours - theirs)


def verdict(reports: list[dict]) -> dict:
    """The spec's pass bars, over every pair."""
    wins: dict[str, bool] = {}
    for trait in ZONE_TRAITS:
        gaps: dict[str, list[float]] = {"today": [], "colourist": []}
        for report in reports:
            theirs = report["reference_summary"].get(trait)
            if theirs is None or "colourist" not in report:
                continue
            for name in gaps:
                ours = report[name].get(trait)
                if ours is not None:
                    gaps[name].append(_distance(trait, ours, theirs))
        if gaps["today"] and gaps["colourist"]:
            wins[trait] = float(np.mean(gaps["colourist"])) < float(np.mean(gaps["today"]))
    zoned = [r["colourist"] for r in reports if "colourist" in r]
    within = lambda value, limit: value is None or abs(value) <= limit
    return {
        "trait_wins": wins,
        "wins": sum(wins.values()),
        "face_ok": all(within(r["face_l_change"], FACE_LIMIT) for r in zoned),
        "seam_ok": all(within(r["seam"], SEAM_LIMIT) for r in zoned),
        "flicker_ok": all(r[k] is None or r[k] <= FLICKER_LIMIT for r in zoned for k in ("flicker_room", "flicker_face")),
        "fallback_pairs": [f"{r['take']} x {r['reference']}" for r in reports if "colourist" not in r],
    }


def _cached_mattes(takes: list[str], out_dir: pathlib.Path) -> dict[str, TakeMatte]:
    found: dict[str, TakeMatte] = {}
    missing: list[str] = []
    for take in takes:
        stem = pathlib.Path(take).stem
        subject, skin = out_dir / f"{stem}.subject.mp4", out_dir / f"{stem}.skin.mp4"
        if subject.exists() and skin.exists():
            found[take] = TakeMatte(subject=str(subject.resolve()), skin=str(skin.resolve()))
        else:
            missing.append(take)
    if missing:
        found.update(matte_takes(missing, out_dir))
    return found


def _cached_fingerprint(reference: str, out_dir: pathlib.Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{pathlib.Path(reference).stem[:40]}.json"
    if path.exists():
        return json.loads(path.read_text())
    measured = extract_fingerprint(reference, stride=3).as_dict()
    path.write_text(json.dumps(measured))
    return measured


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the colourist grade against today's, takes x references.")
    parser.add_argument("--takes", nargs="+", required=True)
    parser.add_argument("--references", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cache", default="", help="where mattes and fingerprints are kept (default: --out)")
    parser.add_argument("--strength", type=float, default=None)
    parser.add_argument("--choke", type=float, default=None, help="grade matte choke, share of height")
    parser.add_argument("--feather", type=float, default=None, help="grade matte feather, share of height")
    args = parser.parse_args(argv)
    out = pathlib.Path(args.out)
    cache = pathlib.Path(args.cache) if args.cache else out
    mattes = _cached_mattes(args.takes, cache / "mattes")
    reports = []
    for reference in args.references:
        fingerprint = _cached_fingerprint(reference, cache / "references")
        for take in args.takes:
            pair = out / f"{pathlib.Path(take).stem[:24]}__{pathlib.Path(reference).stem[:24]}"
            report = evaluate_pair(take, mattes[take], fingerprint, pair,
                                   args.strength, args.choke, args.feather)
            reports.append(report)
            made = report.get("colourist")
            print(f"{pair.name}: colourist={'yes' if made else 'fallback'}"
                  + (f" face {made['face_l_change']} seam {made['seam']} "
                     f"flicker {made['flicker_room']}/{made['flicker_face']}" if made else ""))
    summary = {"pairs": reports, "verdict": verdict(reports)}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary["verdict"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to see them pass.** Run `"$PY" -m pytest tests/test_grade_eval.py -q`. Expected: 5 passed.

- [ ] **Step 5: Run the full suite.** Run `"$PY" -m pytest -q`. Expected: all pass. The count is Task 0's baseline plus the new tests.

- [ ] **Step 6: Commit.**

```bash
git add packages/pipeline/halfheaven/analyze/grade_eval.py packages/pipeline/tests/test_grade_eval.py
git commit -m "feat(grade): evaluate the colourist grade against today's across takes and references"
```

---

### Task 11: Evaluate, tune, and get sign-off

This task runs the real matrix and decides the defaults. Commit a code change only where a step says to.

**Files:** possibly `packages/pipeline/halfheaven/schemas.py` (the `ZoneGrade` choke and feather defaults, or the `GradeProfile.strength` default) and `render/video.py` (`tmix`), per the decisions below.

- [ ] **Step 1: Run the matrix at today's strength.** From the workspace root, with the media still in the main checkout:

```bash
M="/Users/landerstudio/Desktop/untitled folder/halfheaven"
cd packages/pipeline
"$PY" -m halfheaven.analyze.grade_eval \
  --takes "$M/noedit.mp4" "$M/WhatsApp Video 2026-09-26 at 1.13.43 PM.mp4" "$M/raw.mp4" \
  --references "$M/day 4 of teaching myself to color grade, and we’re talking about SCOPES!featuring the gorgeous s.mp4" \
               "$M/tap the corner to watch the full tutorials !! 🌟trying out the new linked reels feature and it’s.mp4" \
               "$M/edited.mp4" \
               "$M/Day 3 building brand from Abbottbad...Follow me Mari jann...#abbotabad #brandbuilder #branding #.mp4" \
               "$M/insta.mp4" \
  --out "$M/work/grade_eval_070" --cache "$M/work/grade_eval_cache" --strength 0.7
```

Expected: 15 pair lines. The `insta.mp4` pairs report `fallback`. A verdict JSON follows.

- [ ] **Step 2: Run it again at 0.85**, with `--out "$M/work/grade_eval_085" --strength 0.85`. The cache makes mattes and fingerprints free the second time.

- [ ] **Step 3: Check the pass bars from both `summary.json` files.**
  - `wins >= 4`
  - `face_ok`, `seam_ok` and `flicker_ok` are all true
  - `fallback_pairs` lists exactly the three `insta.mp4` pairs
  - On the noedit pairs, `colourist.render_seconds - today.render_seconds <= 15`

  - Run the full pipeline once, `"$PY" -m halfheaven.cli --reference <day 4 reel> --target "$M/noedit.mp4" --out "$M/work/cg_full.mp4" --work "$M/work/cg_full"`, under `time`. It must print a `colourist grade:` line, and its wall-clock must stay inside the 3-minute budget. noedit is 61s against a budget set for 2-minute takes, so it should finish well under.

- [ ] **Step 4: If `seam_ok` fails**, rerun at the better strength with `--choke 0.003 --feather 0.008`, then `--choke 0.008 --feather 0.005`.
  - If one passes, set those values as the `ZoneGrade` defaults in `schemas.py`, rerun `"$PY" -m pytest -q`, and commit: `fix(grade): tune the grade matte's choke and feather`.
  - If none passes, stop. Report to the user that colour unmixing (RVM's foreground estimate) is needed, as its own spec.

- [ ] **Step 5: If `flicker_ok` fails on `flicker_face`**, the skin matte is refreshed every third frame. In `grade_filters`, change the skin matte step to `f"{skin}format=gray,tmix=frames=3,lut=c0='val*{grade.skin_weight:.3f}'[zkm]"`. Add a command test asserting `"tmix=frames=3" in graph_of(command)` to `test_the_colourist_grade_runs_three_luts_through_the_mattes`. Rerun the suite and the matrix, and commit: `fix(grade): steady the skin matte the grade reads`.

- [ ] **Step 6: Choose the default strength.** Keep the strength with more trait wins, where both pass every other bar.
  - If that is 0.85, change the `GradeProfile.strength` default in `schemas.py` from `0.7` to `0.85`. Update the comment to say the colourist grade was tuned at 0.85, rerun `"$PY" -m pytest -q`, and commit: `feat(grade): default strength 0.85, tuned on the evaluation matrix`.

- [ ] **Step 7: The user's visual sign-off.**
  - Rebuild the comparison page from `raw_a.jpg`, `today_a.jpg` and `colourist_a.jpg` (and the `_b` stills) in every pair folder of the chosen run, with the verdict numbers.
  - Publish it as an update to https://claude.ai/artifact/4To2ARdXFdLDVabkDqmKTr.
  - Ask the user to approve. Their second open question (default on, or behind a toggle) is answered here. Their first (more takes) can extend the matrix before merge.

- [ ] **Step 8: Finish.** Run `"$PY" -m pytest -q` (all pass), then use superpowers:finishing-a-development-branch.
