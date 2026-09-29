# Colourist grade

Date: 2026-09-26. Status: design, awaiting review.
Spike: https://claude.ai/artifact/4To2ARdXFdLDVabkDqmKTr (throwaway code, not in the repo).

## Goal

Replace the grade's single statistical LUT with a grade that works the way a colourist does. First, correct the creator's footage. Then read the reference's look as named controls: tone curve, tints, saturation and skin placement. Read them separately for the subject and the background, and apply them per zone through the subject and skin mattes that already exist.

Success means the output looks like the reference's grade more often than today's does, measured by the scorecard across several reference/take pairs. It must do this without changing the creator's face brightness, and without visible seams or flicker at the matte edge.

## Why

Today's grade (`render/lut.py`) matches the mean and spread of each LAB channel over the whole frame. That is a straight line per channel: it cannot bend a tone curve, tint shadows differently from highlights, or move the room without moving the face. Measured on the spike (WhatsApp take toward the "day 4" colour-grade reel):

| | face above background | background L | face L |
|---|---|---|---|
| raw | −16.6 | 53.5 | 37.8 |
| today's grade | −3.4 | 29.6 | 27.2 (muddy) |
| colourist spike | +18.7 | 14.1 | 37.1 |
| reference | +28.8 | 8.9 | (hers) |

## Rules that do not bend

1. **The creator's face keeps its own brightness.** Skin L is pinned to the corrected footage. Separation from the room is reached by moving the background, never by lightening or darkening skin toward the reference's person.
   *Revised 2026-09-29:* a face held still read as ungraded against a graded room. The face now moves toward the reference's face by at most +8 / −4 L, as an exposure change with the whole subject moving with it. Skin keeps its hue and richness, so this is never a fairness filter. Skin takes no split tone, and the subject takes the room's split tone, never its own clothes'.
2. **Every control is bounded** (table below). A reference can never push footage further than the bounds, whatever it contains.
3. **Strength 0 is the identity.** `GradeProfile.strength` (the chat's `grade.strength` knob) scales every control.
4. **No mattes, no zones.** If the reference has no person or any take lacks a subject or skin matte, today's global LUT runs unchanged.

## Non-goals (this spec)

- Per-take correction and steadying skin brightness over time (both need time-varying ops, not a LUT).
- Studio sliders or chat knobs for the named controls. The controls are stored in the program so these can come next.
- Depth-based background falloff, lens blur, learned colour transfer, relighting.
- Changing the `/lab` readout copy.

## Design

### 1. Reading zones: `analyze/zones.py` (new)

One function reads the same `ZoneLook` from any footage, given per-frame masks:

```
ZoneLook
  subject, background: ZoneTone
      l_quantiles: 101 floats   # L at percentiles 0..100
      median_chroma: float
      tints: 6 x (a, b)         # near-neutral tint per L band
  skin: SkinTone | None
      ab: (a, b)                # mean
      median_l: float
```

- **Near-neutral tint:** pixels with chroma < 15, grouped by L bands `[0, 12, 25, 40, 55, 70, 101]`. A band with fewer than 300 pixels takes the zone's overall near-neutral mean (or 0 when that has fewer than 200).
- Frames are read at ≤ 640 px on the long side. Colour statistics survive downscaling (the fingerprint's "downscaling destroys text" trap does not apply).
- **The reference** gets masks from MediaPipe parts. Subject is the person eroded by 0.5% of frame height. Background is outside the person dilated by the same amount, so the edge band counts in neither zone. Skin is the face-skin and body-skin classes. It runs on the photographic frames `_grade` already picks (≤ 60). `ZoneLook` is absent when fewer than 10 of those frames contain a person covering ≥ 5% of the frame.
- **The takes** get masks from their own mattes: subject α > 0.9, background α < 0.1, skin weight > 0.6. Read 16 frames per take, at most 48 in total, pooled across takes.

Pixel math is in OpenCV float LAB (L 0–100), as `render/lut.py` already uses.

### 2. Planning controls: `plan/colourist.py` (new)

`plan_grade(take: ZoneLook, ref: ZoneLook, strength: float) -> GradeControls` is a pure function with no I/O. `s` is strength.

| step | control | how | bound |
|---|---|---|---|
| correct | white balance | Rotate the take's skin hue toward the reference's by `dh = clip(h_ref − h_take, ±12°) × 0.8`. Applied as one (a, b) offset to every pixel: `C_take·(cos(h_take+dh), sin(h_take+dh)) − ab_take`, × s | ±12° |
| look | exposure anchor `k` | `median skin L (take, corrected) / median skin L (ref)`. The reference's tonal layout is scaled by `k` so its skin sits where this creator's already is | 0.7–1.5 |
| look | tone curve, per zone | Quantile map from the take's zone L to `k ×` the reference's zone L, on a 201-point grid, 13-point box smoothing. Slope clipped, then shifted so the take's median still maps where the unclipped curve put it. `L' = L + s·(T(L) − L)` | slope 0.12–1.6 |
| look | saturation, per zone | Ratio of median chroma, reference over take. `ab × (1 + s·(sat − 1))` | subject 0.85–1.15, background 0.8–1.3 |
| look | tints, per zone | `ab + s·(tint_ref(L'/k) − tint_take(L))` | from measured tables |
| skin | skin richness `c` | Reference skin chroma over the take's skin chroma after the subject ops. `ab × (1 + s·(c − 1))`; L pinned to the corrected L | 0.85–1.3 |

Why each bound exists, from the spike:
- **Slope limit:** an unlimited curve turned h264 blocks on a white wall into visible patches, the same reason CLAHE clips its histogram. The low floor still allows the room to be crushed.
- **Lamps are content:** the reference's brightest background pixels are often a practical light. The slope limit is what stops the grade stretching a plain wall up to lamp brightness.
- **White balance from skin:** grey-world white balance failed on a cream wall and a blue shirt, so white balance is aimed from skin, and capped.
- **Skin pinning:** a subject-zone tone curve darkened skin along with a bright shirt. That is why rule 1 pins skin brightness.

`GradeControls` is a pydantic model holding every value above, curves included, so it can be stored, printed and edited later.

### 3. Baking: `render/lut.py`

`write_zone_luts(controls, out_dir) -> ZoneGrade` writes three 33³ `.cube` files through one shared numpy function, `apply_controls(rgb, controls, zone)`:

- `subject.cube`: correct → subject tone, saturation, tints.
- `background.cube`: correct → background tone, saturation, tints.
- `skin.cube`: subject ops, then L reset to the corrected L and chroma × `(1 + s·(c − 1))`.

Every op is a function of pixel colour alone, so each zone is exactly one LUT. The existing `transfer`/`write_lut` stay for the fallback.

### 4. Rendering: `render/video.py`

The finish pass's grade step becomes a shared helper, `grade_filters(look, subject, skin) -> list[str]`. Order within the pass is unchanged: grade → background replacement → letterbox → captions.

```
[in] split=3 [s][b][k]
[b] lut3d=background                                   -> [vb]
[s] lut3d=subject, format=yuva420p                     -> [vs]
[subject matte] gray, shrink by choke, gblur feather   -> [gm]
[vs][gm] alphamerge -> [vsa];  [vb][vsa] overlay        -> [vz]
[k] lut3d=skin, format=yuva420p                        -> [vk]
[skin matte] gray, ×0.9                                -> [km]
[vk][km] alphamerge -> [vka];  [vz][vka] overlay        -> [vg]
```

- **The grade matte** is the subject track shrunk by `choke = 0.5%` of frame height and feathered by `sigma = 0.5%`, both stored in `ZoneGrade`. Shrinking puts any rim on the subject's side of the edge rather than the wall's.
- **The subject matte is read once**, then split between its users: grade, behind-captions and background replacement.
- `render()` builds the skin track whenever `look.zone_grade` is set, in addition to the case it covers today.
- **Previews** (`previews.background`) grade their frame through the same helper, using `mask_track` (already cached in the work dir). Caption-look previews then show the picture the render will produce.

### 5. Schemas and wiring

- **`schemas.py`**
  - New `ZoneGrade`: `subject_lut`, `background_lut`, `skin_lut`, `skin_weight=0.9`, `choke_pct`, `feather_pct`, `controls: GradeControls`.
  - New field `Look.zone_grade: ZoneGrade | None`.
  - New field `GradeProfile.zones: dict | None`, holding the reference `ZoneLook`.
  - `Look.skin_protect` stays for the fallback path only.
- **`analyze/fingerprint.py`**
  - `Grade` gains five scalar readings: `face_above_background`, `background_l`, `skin_chroma`, `skin_hue`, `shadow_tint`. Each is `absent` when zones are.
  - The full `ZoneLook` table goes in a new top-level `zone_look` key, not in `grade`. The `/lab` readout lists every `grade` reading under "numbers", and a 600-number table has no place there.
- **`plan/typography.py`**: `_apply_grade` copies the fingerprint's `zone_look` into `GradeProfile.zones`.
- **`cli.py`**
  - After `matting.result()`: when `profile.grade.zones` and mattes exist, read the takes' `ZoneLook`, plan, bake, and set `look.zone_grade`. Otherwise run today's path.
  - Keep printing the `grade LAB mean` / `grade: target LAB mean` lines: the studio's "Yours / Theirs" swatches parse them (`apps/web/src/lib/pipeline.ts`).
  - Add one line that prints the controls.
- **`analyze/compare.py`**: new traits.

| trait | distance | match / near |
|---|---|---|
| face above background | abs L | 6 / 12 |
| background brightness | abs L | 6 / 12 |
| skin richness | abs chroma | 4 / 8 |
| skin hue | abs degrees | 6 / 12 |
| shadow tint | abs a* | 2 / 4 |

### 6. Edge and flicker

Two metrics, computed on output frames against the raw footage over the same frames.

- **Seam.**
  - Take the subject matte's 0.5 contour, with rings measured in % of frame height: edge (±0.35%), inner (0.5–1.4% inside) and outer (0.5–1.4% outside).
  - `seam = mean L(edge) − (mean L(inner) + mean L(outer)) / 2`. Positive is a bright rim, negative a dark line.
  - Pass: `|seam_out − seam_raw| ≤ 2.0 L`, averaged per pair.
- **Flicker.**
  - Between consecutive frames, take background pixels that are static in the raw (`|ΔL_raw| < 1`) and compute the mean `|ΔL_out|`. Do the same for the face's median L.
  - Pass: each is at most 1.0 L above the raw's.

What happens if they fail:
- **Seam fails at every choke/feather tried:** switch to colour unmixing. RVM already estimates the foreground colour. Write it beside the matte, and grade foreground and background colours separately at the edge. This is a bigger change and would come back as its own spec.
- **Flicker fails on skin:** the skin matte is refreshed every third frame. Add a 3-frame temporal average (`tmix`) to the grade's copy of the skin matte.

## Evaluation

A module, `python -m halfheaven.analyze.grade_eval` (alongside `compare` and `fingerprint`), runs the real pipeline on every take × reference pair, once with today's grade and once with the colourist grade. It then writes the scorecard traits, the face-brightness check, the seam and flicker metrics, and wall-clock time.

- **Takes:** `noedit.mp4` (720×1280, 61s), the WhatsApp take (768×576, 19s) and `raw.mp4` (2160×3840, 22s). That is three creators with different skin tones and lighting.
- **References:**
  - "day 4" colour-grade reel
  - "tap the corner"
  - `edited.mp4`
  - Day 3 (a test input only, not a target)
  - `insta.mp4`, which has no person and must take the fallback

Pass bars, all required:

1. On the zone traits averaged across pairs, the colourist grade beats today's grade on at least 4 of 5.
2. Face L within ±2 of raw on every pair.
3. Seam and flicker bars hold on every pair.
4. `insta.mp4` pairs take the fallback: no `zone_grade`, and the same single LUT today's code bakes.
5. The whole pipeline stays inside the 3-minute budget for a 2-minute take. The grade may add at most 15 s to the finish pass for a 61 s take.
6. **The user signs off visually.** The spike page is regenerated from the real renders (frames from the finished videos, not stills graded in numpy) across the matrix.

The default strength is tuned during evaluation (the spike used 0.85; today's default is 0.7).

## Unit tests

- **`zones`:** synthetic frames with known zone colours give the expected quantiles, tints and skin values. A frame without a person gives `absent`.
- **`colourist`:**
  - Every bound holds for adversarial inputs (a black reference, a white one, a reference with no neutrals).
  - Curves are monotone and slope-limited.
  - Strength 0 gives identity controls.
  - Equal take and reference looks give near-identity controls.
- **`lut`:** identity controls bake to an identity LUT (max error < 1/255). The skin LUT leaves L equal to the corrected L.
- **`video`:** the finish command contains the three `lut3d` passes, reads the subject matte exactly once when behind-captions and background replacement are also on, and falls back to the single LUT without mattes (same pattern as `test_render_command.py`).
- **`compare`:** new traits score `unscored` when either side is absent.

## Risks

- **Skin mask accuracy on darker skin.** MediaPipe's worst skin-tone group scored IoU 71.9. The test set has three creators, which is thin evidence. See the first open question.
- **Content mistaken for the grade.** A red sofa in the reference is not near-neutral, so it does not become a red tint. The zone tone curves still carry some content, for example a room that really is dark. The bounds limit how far this reaches.
- **Render time.** There are three LUT branches and two extra overlays. This is measured in evaluation, not assumed.

## Open questions for the user

1. **Before this becomes the default, can you record two or three short takes** with a different skin tone, daylight or mixed lighting, and a busy background? That makes six creators and setups instead of three.
2. **Default on when the pass bars hold (my recommendation), or behind a toggle first?**
