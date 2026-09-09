"""Role-based font resolution.

Identifying a specific typeface from pixels is unreliable, so the vision pass
classifies a *category* and this module maps that category onto a font we are
entitled to embed. We match the reference's character, not its exact typeface -
an honest limitation, and the alternative is shipping fonts we have no licence
for.

The paths below are macOS system fonts, which is fine for local work and wrong
for a deployed worker. Replacing this table with bundled, licensed families is
the only change needed: nothing else in the renderer knows where a font came
from.
"""
from __future__ import annotations

import functools
import os
import pathlib

from PIL import ImageFont

_SEARCH_DIRS = (
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/local/share/fonts",
)

# Ordered by preference; the first that exists on this machine wins.
CATEGORY_CANDIDATES: dict[str, tuple[str, ...]] = {
    # uniform stroke, fixed pitch - the reference's running-caption face
    "mono": ("Andale Mono.ttf", "Menlo.ttc", "Courier New Bold.ttf", "DejaVuSansMono-Bold.ttf"),
    # neutral workhorse sans
    "grotesque": ("HelveticaNeue.ttc", "Helvetica.ttc", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"),
    # circular, geometric sans
    "geometric": ("Futura.ttc", "Avenir Next.ttc", "DejaVuSans-Bold.ttf"),
    # thick stems, hairline serifs - the reference's emphasis face
    "didone": ("Bodoni 72.ttc", "Didot.ttc", "BigCaslon.ttf", "DejaVuSerif-Bold.ttf"),
    # squared slab serifs
    "slab": ("AmericanTypewriter.ttc", "Georgia Bold.ttf", "DejaVuSerif-Bold.ttf"),
    # heavy condensed poster type
    "display": ("Impact.ttf", "Arial Black.ttf", "DejaVuSans-Bold.ttf"),
}

CATEGORIES = tuple(CATEGORY_CANDIDATES)
FALLBACK_CATEGORY = "grotesque"


def _first_existing(names: tuple[str, ...]) -> pathlib.Path | None:
    for name in names:
        for directory in _SEARCH_DIRS:
            candidate = pathlib.Path(directory) / name
            if candidate.exists():
                return candidate
    return None


@functools.lru_cache(maxsize=None)
def resolve_font_path(category: str) -> pathlib.Path:
    """A usable font file for `category`, never raising.

    An unknown or unavailable category degrades to the fallback rather than
    failing the render: a caption in the wrong face is recoverable, a crashed
    job is not.
    """
    found = _first_existing(CATEGORY_CANDIDATES.get(category, ()))
    if found is None:
        found = _first_existing(CATEGORY_CANDIDATES[FALLBACK_CATEGORY])
    if found is None:
        # Last resort: anything the system will give us.
        for directory in _SEARCH_DIRS:
            path = pathlib.Path(directory)
            if path.is_dir():
                for entry in sorted(os.listdir(path)):
                    if entry.lower().endswith((".ttf", ".ttc", ".otf")):
                        return path / entry
        raise RuntimeError("no usable font found on this system")
    return found


@functools.lru_cache(maxsize=256)
def load_font(category: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(resolve_font_path(category)), size)
