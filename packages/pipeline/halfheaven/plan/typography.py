"""Setting type the way the reference set it.

The fingerprint measures how a reference's captions look. This turns those
measurements into the caption styles the renderer draws, and into a plan for how
type is used across the edit. It is the step that was missing: the extraction
reported italic, colour, size and position, and the render never read any of
it. It drew defaults whenever the older analyzer found no stable subtitle band -
which, on an editorial reference, is always.

Two conversions are calibrated rather than assumed, both by rendering known
values through the real caption renderer and reading them back with the
fingerprint's own instruments:

  size    the fingerprint measures glyph height; the renderer takes font size.
          Glyph height is 0.684 of font size - the median over five faces at
          three sizes, with the sans faces within about 3% of it.
  weight  the fingerprint measures stroke width over glyph height, which climbs
          evenly with weight: 0.085 at 300, 0.152 at 500, 0.238 at 700, 0.314
          at 900, and two different faces agree to within 0.01.

Every value is clamped to a range that stays legible on a phone. Extraction
proposes; these limits are where art direction disposes.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from halfheaven.render.fonts import choose, counterpart
from halfheaven.schemas import StyleProfile, TypePlan

GLYPH_TO_SIZE = 0.684
WEIGHT_READINGS = (0.085, 0.152, 0.238, 0.314)
WEIGHTS = (300, 500, 700, 900)

# Below this a caption cannot be read on a phone at arm's length; above it the
# type stops being a caption and becomes the frame.
MIN_SIZE = 0.028
MAX_SIZE = 0.11
# A stressed word in another face needs a little more size to carry the same
# weight. Used only when the faces are unknown; otherwise the stressed word is
# sized by the height of its lowercase letters against the body's.
EMPHASIS_SCALE = 1.25
# How much taller than the body's lowercase a stressed word's lowercase stands.
EMPHASIS_LIFT = 1.15
MAX_EMPHASIS_SIZE = 0.13
# The reference's time on screen is honoured, but never below this: a talking
# piece with type up a quarter of the time reads as missing captions.
MIN_DUTY = 0.35


def _value(section: dict[str, Any], name: str) -> Any:
    """A reading's value, or None when it was looked for and not found."""
    reading = section.get(name) or {}
    if reading.get("confidence") == "absent":
        return None
    return reading.get("value")


def _apply_grade(profile: StyleProfile, fingerprint: dict[str, Any]) -> StyleProfile:
    """The colour target, taken from the fingerprint's photographic frames.

    The older analyzer averages every frame, title cards included, so a reference
    with deep red cards reads as red and tints the target's skin magenta. The
    fingerprint excludes graphics before measuring, which is the whole reason it
    measured Day 3 as neutral (a* +0.4) where the analyzer said +8.2.
    """
    grade = fingerprint.get("grade") or {}
    mean, spread = _value(grade, "lab_mean"), _value(grade, "lab_std")
    if not mean or not spread:
        return profile
    return profile.model_copy(update={"grade": profile.grade.model_copy(update={
        "measured": True,
        "lab_mean": tuple(float(v) for v in mean),
        "lab_std": tuple(float(v) for v in spread),
    })})


def apply_fingerprint(profile: StyleProfile, fingerprint: dict[str, Any]) -> StyleProfile:
    """The profile with its colour and captions set the way the reference sets them."""
    profile = _apply_grade(profile, fingerprint)
    text = fingerprint.get("text") or {}
    duty = _value(text, "duty_cycle")
    if duty is None:
        return profile      # the reference carries no type to copy

    contrast, italic = _value(text, "contrast"), _value(text, "italic")
    face = choose(contrast=contrast, italic=italic) if contrast is not None else None
    partner = counterpart(face) if face else None

    size = profile.captions.size_pct
    glyph = _value(text, "size_pct")
    if glyph:
        size = float(np.clip(glyph / GLYPH_TO_SIZE, MIN_SIZE, MAX_SIZE))

    weight = profile.captions.font_weight
    stroke = _value(text, "weight")
    if stroke:
        weight = int(round(float(np.interp(stroke, WEIGHT_READINGS, WEIGHTS)) / 50) * 50)

    centroid = _value(text, "centroid") or profile.captions.anchor
    centroid = (float(centroid[0]), float(centroid[1]))
    fill = _value(text, "fill_hex") or profile.captions.fill_hex
    # When the treatment could not be judged, a soft shadow rather than the
    # default heavy outline: the outline is the loudest tell of burned-in
    # subtitles, and a soft shadow keeps type legible while barely showing.
    decor = _value(text, "decor") or "shadow_soft"
    caps = _value(text, "all_caps")
    caps = profile.captions.all_caps if caps is None else bool(caps)
    accent = _value(text, "accent_hex")

    # A stressed word must stand at least as tall as the body it interrupts,
    # measured on its lowercase letters. A flat multiple ignores that a script's
    # letters are small for its size: Sacramento's are 40% shorter than
    # Archivo's, so 1.25x set the stressed word *smaller* than the words round it.
    emphasis_size = size * EMPHASIS_SCALE
    if face and partner:
        emphasis_size = size * face.x_height / partner.x_height * EMPHASIS_LIFT

    body = profile.captions.model_copy(update={
        "present": True,
        "font_file": face.file if face else profile.captions.font_file,
        "font_category": face.category if face else profile.captions.font_category,
        "font_weight": weight,
        "size_pct": size,
        "all_caps": caps,
        "fill_hex": fill,
        "decor": decor,
        "anchor": centroid,
    })
    emphasis = profile.emphasis.model_copy(update={
        "present": True,
        "font_file": partner.file if partner else profile.emphasis.font_file,
        "font_category": partner.category if partner else profile.emphasis.font_category,
        "font_weight": weight,
        "size_pct": float(min(emphasis_size, MAX_EMPHASIS_SIZE)),
        # a script set in capitals is illegible, and no one sets one that way
        "all_caps": False if (partner and partner.genre == "script") else caps,
        "fill_hex": accent or fill,
        "decor": decor,
        "anchor": centroid,
    })
    plan = TypePlan(
        duty_cycle=float(min(1.0, max(MIN_DUTY, duty))),
        placement=_value(text, "placement") or "fixed",
        centroid=centroid,
        spread=float(_value(text, "spread") or 0.0),
        # without an accent colour there is nothing for a stressed word to turn
        accent_rate=float(_value(text, "accent_rate") or 0.0) if accent else 0.0,
    )
    return profile.model_copy(update={"captions": body, "emphasis": emphasis, "type_plan": plan})


def describe(profile: StyleProfile) -> str:
    """One line for the log, so a render says what it copied."""
    body, emphasis, plan = profile.captions, profile.emphasis, profile.type_plan
    name = lambda style: (style.font_file or style.font_category).removesuffix(".ttf")
    line = (f"type: {name(body)} {body.font_weight} at {body.size_pct:.3f}, {body.decor}; "
            f"stressed words in {name(emphasis)} {emphasis.fill_hex}")
    if plan:
        line += (f"; {plan.placement}, on screen {plan.duty_cycle:.0%}, "
                 f"accent on {plan.accent_rate:.0%} of cards")
    return line
