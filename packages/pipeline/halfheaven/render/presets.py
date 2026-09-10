"""Named caption looks, composed from the axes.

Each is a handful of fields over the same renderer. The descriptions are what a
creator sees, so they name the effect rather than the settings.
"""
from __future__ import annotations

from typing import Any

from halfheaven.schemas import CaptionProfile

CAPTION_PRESETS: dict[str, dict[str, Any]] = {
    # The dominant short-form look: chunky caps, the spoken word lit up.
    "hormozi": {
        "label": "Word pop",
        "blurb": "Chunky caps, the word you're saying lights up",
        "font_category": "grotesque", "font_weight": 900, "size_pct": 0.072,
        "grouping": "phrase", "max_words": 4, "reveal": "karaoke",
        "enter": "pop", "active": "colour", "active_fill_hex": "#FFE94A",
        "decor": "stroke", "stroke_heavy": True, "all_caps": True,
        "fill_hex": "#FFFFFF", "anchor": (0.5, 0.70),
    },
    # Huge single words with a hard offset shadow.
    "beast": {
        "label": "Big and loud",
        "blurb": "One huge word at a time with a hard shadow",
        "font_category": "display", "size_pct": 0.115,
        "grouping": "single", "max_words": 1, "reveal": "append",
        "enter": "pop", "pop_from": 0.7, "active": "none",
        "decor": "shadow_hard", "shadow_hex": "#000000", "shadow_offset_pct": 0.09,
        "all_caps": True, "fill_hex": "#FFFFFF", "anchor": (0.5, 0.5),
    },
    # What the reference in this repo actually does: small, quiet, no motion.
    "documentary": {
        "label": "Quiet",
        "blurb": "Small, calm captions that stay out of the way",
        "font_category": "mono", "font_weight": 500, "size_pct": 0.05,
        "grouping": "phrase", "max_words": 6, "reveal": "append",
        "enter": "none", "active": "none",
        "decor": "stroke", "stroke_heavy": False,
        "all_caps": False, "fill_hex": "#F2E9C9", "anchor": (0.5, 0.73),
    },
    # Each word in its own rounded chip.
    "sticker": {
        "label": "Stickers",
        "blurb": "Every word on its own rounded chip",
        "font_category": "rounded", "font_weight": 800, "size_pct": 0.062,
        "grouping": "phrase", "max_words": 3, "reveal": "append",
        "enter": "pop", "active": "none",
        "decor": "pill", "box_hex": "#101010", "box_alpha": 0.82, "box_radius_pct": 0.42,
        "all_caps": False, "fill_hex": "#FFFFFF", "anchor": (0.5, 0.74),
    },
    # A highlighter bar sweeping under the spoken word.
    "highlighter": {
        "label": "Highlighter",
        "blurb": "A marker sweeps under each word as it's said",
        "font_category": "grotesque", "font_weight": 800, "size_pct": 0.066,
        "grouping": "phrase", "max_words": 4, "reveal": "karaoke",
        "enter": "none", "active": "marker", "active_box_hex": "#22C55E",
        "decor": "stroke", "stroke_heavy": False,
        "all_caps": False, "fill_hex": "#FFFFFF", "anchor": (0.5, 0.72),
    },
    # Words stacked down the middle, one per line.
    "stacked": {
        "label": "Stacked",
        "blurb": "Words build down the middle of the frame",
        "font_category": "condensed", "size_pct": 0.085,
        "grouping": "phrase", "max_words": 3, "reveal": "append",
        "enter": "pop", "active": "scale", "active_scale": 1.14,
        "decor": "stroke", "stroke_heavy": True, "layout": "stack",
        "all_caps": True, "fill_hex": "#FFFFFF", "anchor": (0.5, 0.62),
    },
    # Legible over anything: solid panel behind the card.
    "subtitle": {
        "label": "Subtitle bar",
        "blurb": "A solid bar behind the text, readable on anything",
        "font_category": "neutral", "font_weight": 600, "size_pct": 0.046,
        "grouping": "phrase", "max_words": 7, "reveal": "instant",
        "enter": "none", "active": "none",
        "decor": "box", "box_hex": "#000000", "box_alpha": 0.66, "box_radius_pct": 0.14,
        "all_caps": False, "fill_hex": "#FFFFFF", "anchor": (0.5, 0.82),
    },
}

FALLBACK = "hormozi"


def preset(name: str) -> CaptionProfile:
    """A profile for a named look, falling back rather than raising."""
    fields = CAPTION_PRESETS.get(name) or CAPTION_PRESETS[FALLBACK]
    settings = {k: v for k, v in fields.items() if k not in ("label", "blurb")}
    return CaptionProfile(present=True, **settings)


def catalogue() -> list[dict[str, str]]:
    """What the picker shows: the name and what it does, in plain words."""
    return [
        {"id": key, "label": str(value["label"]), "blurb": str(value["blurb"])}
        for key, value in CAPTION_PRESETS.items()
    ]
