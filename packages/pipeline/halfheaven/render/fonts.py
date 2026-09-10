"""Type, by role rather than by name.

Identifying a specific typeface from pixels is unreliable, so the vision pass
classifies a *category* and this maps it to a face we ship. We match character,
not typeface.

Every face here is a file in the repo under OFL or Apache-2.0 - licences that
permit embedding and redistribution. The first version of this pointed at macOS
system fonts, which cannot ship: they are not ours to embed, and a Linux worker
does not have them.

Several are variable fonts, whose default instance is 400. At caption size that
reads as weak, so weight is set explicitly rather than accepted.
"""
from __future__ import annotations

import functools
import pathlib

from PIL import ImageFont

ASSET_DIR = pathlib.Path(__file__).resolve().parent.parent / "assets" / "fonts"

# Category -> file. Chosen for what creators actually reach for: Montserrat is
# the caption face of most viral short-form, Anton and Bebas the poster faces.
CATEGORY_FILES: dict[str, str] = {
    "grotesque": "Montserrat.ttf",           # the workhorse caption face
    "neutral": "Inter.ttf",
    "geometric": "Poppins-ExtraBold.ttf",
    "display": "Anton-Regular.ttf",          # heavy poster type
    "condensed": "BebasNeue-Regular.ttf",
    "mono": "JetBrainsMono.ttf",
    "didone": "PlayfairDisplay.ttf",         # thick stems, hairline serifs
    "slab": "RobotoSlab.ttf",
    "rounded": "Baloo2.ttf",
    "handwritten": "PermanentMarker-Regular.ttf",
}

CATEGORIES = tuple(CATEGORY_FILES)
FALLBACK_CATEGORY = "grotesque"
DEFAULT_WEIGHT = 800


@functools.lru_cache(maxsize=None)
def resolve_font_path(category: str) -> pathlib.Path:
    """A usable font file for `category`, never raising.

    An unknown category degrades to the fallback: a caption in the wrong face
    is recoverable, a crashed render is not.
    """
    name = CATEGORY_FILES.get(category) or CATEGORY_FILES[FALLBACK_CATEGORY]
    path = ASSET_DIR / name
    if path.exists():
        return path
    fallback = ASSET_DIR / CATEGORY_FILES[FALLBACK_CATEGORY]
    if fallback.exists():
        return fallback
    available = sorted(ASSET_DIR.glob("*.ttf"))
    if available:
        return available[0]
    raise RuntimeError(f"no fonts bundled in {ASSET_DIR}")


@functools.lru_cache(maxsize=512)
def load_font(category: str, size: int, weight: int = DEFAULT_WEIGHT) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(resolve_font_path(category)), size)
    try:
        # Variable faces default to 400; single-weight faces have no axes and
        # raise, which is fine - they are already the weight they are.
        font.set_variation_by_axes([float(weight)])
    except (OSError, AttributeError, ValueError):
        pass
    return font
