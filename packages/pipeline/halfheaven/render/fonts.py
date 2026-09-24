"""Type, by the character we can measure rather than by name.

Identifying a specific typeface from pixels is unreliable, so the vision pass
measures *character* - how much the stroke swells through a letter, how heavy
it is, whether it leans - and this module answers with the closest face we
ship. Matching character is achievable; matching a typeface is not, and the
typeface belongs to the reference's brand anyway.

Every face here is a file in the repo under OFL or Apache-2.0 - licences that
permit embedding and redistribution. The first version of this pointed at macOS
system fonts, which cannot ship: they are not ours to embed, and a Linux worker
does not have them.

The library is deliberately wide. A reference set in an editorial italic should
come back as an editorial italic, not as "the serif we have", so each genre
carries romans and italics at several degrees of contrast. Choosing well needs
options to choose between.
"""
from __future__ import annotations

import functools
import pathlib
from dataclasses import dataclass

from PIL import ImageFont

ASSET_DIR = pathlib.Path(__file__).resolve().parent.parent / "assets" / "fonts"


@dataclass(frozen=True)
class Face:
    """One shipped font file, described by what a measurement could see.

    `contrast` is the stroke modulation we would expect to measure from this
    face - near zero for a grotesque, high for a didone or a script. It is what
    lets a measured number pick a face rather than a human picking one.
    """

    file: str
    family: str
    genre: str        # sans | serif | script | mono | display
    category: str     # the coarse name the schema already speaks
    contrast: float   # 0 flat, 1 hairline-to-stem
    italic: bool = False
    condensed: bool = False
    caps_only: bool = False
    # Measured by rendering "xonvmwra" at 100 px, weight 700: the height of the
    # lowercase body and the pen width, each as a fraction of the font size.
    x_height: float = 0.55
    stroke: float = 0.14


LIBRARY: tuple[Face, ...] = (
    # --- sans -------------------------------------------------------------
    Face("Montserrat.ttf", "Montserrat", "sans", "grotesque", 0.059, x_height=0.56, stroke=0.16),
    Face("Montserrat-Italic.ttf", "Montserrat", "sans", "grotesque", 0.067, italic=True, x_height=0.56, stroke=0.144),
    Face("Inter.ttf", "Inter", "sans", "neutral", 0.050, x_height=0.56, stroke=0.14),
    Face("Poppins-ExtraBold.ttf", "Poppins", "sans", "geometric", 0.036, x_height=0.56, stroke=0.2),
    Face("Poppins-Italic.ttf", "Poppins", "sans", "geometric", 0.050, italic=True, x_height=0.57, stroke=0.16),
    Face("Archivo.ttf", "Archivo", "sans", "grotesque", 0.067, x_height=0.56, stroke=0.14),
    Face("Archivo-Italic.ttf", "Archivo", "sans", "grotesque", 0.077, italic=True, x_height=0.55, stroke=0.14),
    Face("ArchivoBlack.ttf", "Archivo Black", "sans", "grotesque", 0.050, x_height=0.55, stroke=0.2),
    Face("DMSans.ttf", "DM Sans", "sans", "neutral", 0.056, x_height=0.55, stroke=0.14),
    Face("DMSans-Italic.ttf", "DM Sans", "sans", "neutral", 0.056, italic=True, x_height=0.55, stroke=0.128),
    Face("Manrope.ttf", "Manrope", "sans", "neutral", 0.037, x_height=0.58, stroke=0.12),
    Face("Figtree.ttf", "Figtree", "sans", "neutral", 0.037, x_height=0.52, stroke=0.14),
    Face("Outfit.ttf", "Outfit", "sans", "geometric", 0.033, x_height=0.51, stroke=0.16),
    Face("SpaceGrotesk.ttf", "Space Grotesk", "sans", "grotesque", 0.029, x_height=0.52, stroke=0.12),
    # --- condensed / display ---------------------------------------------
    Face("BebasNeue-Regular.ttf", "Bebas Neue", "display", "condensed", 0.017,
         condensed=True, caps_only=True, x_height=0.72, stroke=0.1),
    Face("Oswald.ttf", "Oswald", "display", "condensed", 0.050, condensed=True, x_height=0.6, stroke=0.16),
    Face("BarlowCondensed.ttf", "Barlow Condensed", "display", "condensed", 0.031,
         condensed=True, x_height=0.53, stroke=0.14),
    Face("BarlowCondensed-Italic.ttf", "Barlow Condensed", "display", "condensed", 0.023,
         italic=True, condensed=True, x_height=0.53, stroke=0.14),
    Face("Anton-Regular.ttf", "Anton", "display", "display", 0.035, x_height=0.75, stroke=0.18),
    # --- serif: the editorial end ----------------------------------------
    Face("PlayfairDisplay.ttf", "Playfair Display", "serif", "didone", 0.356, x_height=0.54, stroke=0.14),
    Face("PlayfairDisplay-Italic.ttf", "Playfair Display", "serif", "didone", 0.755, italic=True, x_height=0.56, stroke=0.116),
    Face("BodoniModa.ttf", "Bodoni Moda", "serif", "didone", 0.023, x_height=0.48, stroke=0.14),
    Face("BodoniModa-Italic.ttf", "Bodoni Moda", "serif", "didone", 0.379, italic=True, x_height=0.48, stroke=0.128),
    Face("DMSerifDisplay.ttf", "DM Serif Display", "serif", "didone", 0.116, x_height=0.5, stroke=0.14),
    Face("DMSerifDisplay-Italic.ttf", "DM Serif Display", "serif", "didone", 0.585, italic=True, x_height=0.52, stroke=0.12),
    Face("InstrumentSerif.ttf", "Instrument Serif", "serif", "didone", 0.150, x_height=0.52, stroke=0.064),
    Face("InstrumentSerif-Italic.ttf", "Instrument Serif", "serif", "didone", 0.241, italic=True, x_height=0.53, stroke=0.06),
    Face("EBGaramond.ttf", "EB Garamond", "serif", "serif", 0.378, x_height=0.47, stroke=0.14),
    Face("EBGaramond-Italic.ttf", "EB Garamond", "serif", "serif", 0.462, italic=True, x_height=0.45, stroke=0.086),
    Face("CormorantGaramond.ttf", "Cormorant Garamond", "serif", "serif", 0.101, x_height=0.42, stroke=0.1),
    Face("CormorantGaramond-Italic.ttf", "Cormorant Garamond", "serif", "serif", 0.257, italic=True, x_height=0.42, stroke=0.08),
    Face("Lora.ttf", "Lora", "serif", "serif", 0.258, x_height=0.54, stroke=0.14),
    Face("Lora-Italic.ttf", "Lora", "serif", "serif", 0.236, italic=True, x_height=0.52, stroke=0.116),
    Face("RobotoSlab.ttf", "Roboto Slab", "serif", "slab", 0.090, x_height=0.55, stroke=0.14),
    # --- script / hand ----------------------------------------------------
    Face("GreatVibes.ttf", "Great Vibes", "script", "script", 0.100, italic=True, x_height=0.48, stroke=0.056),
    Face("Sacramento.ttf", "Sacramento", "script", "script", 0.30, italic=True, x_height=0.33, stroke=0.04),
    Face("DancingScript.ttf", "Dancing Script", "script", "script", 0.293, italic=True, x_height=0.46, stroke=0.056),
    Face("Satisfy.ttf", "Satisfy", "script", "script", 0.223, italic=True, x_height=0.49, stroke=0.072),
    Face("Pacifico.ttf", "Pacifico", "script", "script", 0.100, x_height=0.47, stroke=0.12),
    Face("Caveat.ttf", "Caveat", "script", "handwritten", 0.047, x_height=0.41, stroke=0.084),
    Face("PermanentMarker-Regular.ttf", "Permanent Marker", "script", "handwritten", 0.045, x_height=0.65, stroke=0.144),
    Face("Baloo2.ttf", "Baloo 2", "sans", "rounded", 0.045, x_height=0.52, stroke=0.14),
    # --- mono -------------------------------------------------------------
    Face("JetBrainsMono.ttf", "JetBrains Mono", "mono", "mono", 0.034, x_height=0.57, stroke=0.12),
    Face("SpaceMono.ttf", "Space Mono", "mono", "mono", 0.050, x_height=0.52, stroke=0.08),
)

BY_FILE = {face.file: face for face in LIBRARY}
CATEGORIES = tuple(dict.fromkeys(face.category for face in LIBRARY))
FALLBACK_CATEGORY = "grotesque"
DEFAULT_WEIGHT = 800

# Kept so callers that still speak in coarse categories get a sensible face.
CATEGORY_FILES: dict[str, str] = {}
for _face in LIBRARY:
    CATEGORY_FILES.setdefault(_face.category, _face.file)


def available() -> list[Face]:
    """The faces actually present on disk, so a missing file is not a crash."""
    return [face for face in LIBRARY if (ASSET_DIR / face.file).exists()]


# A stroke thinner than this share of the font size breaks up at caption size
# once video compression has been through it. Measured: Sacramento, at 0.040,
# set Day 3's stressed word as a hairline nobody could read.
MIN_ACCENT_STROKE = 0.07


def choose(
    contrast: float | None = None,
    italic: bool | None = None,
    condensed: bool | None = None,
    category: str | None = None,
    genre: str | None = None,
    exclude_family: str | None = None,
    min_stroke: float | None = None,
) -> Face:
    """The closest shipped face to a set of measured traits.

    Scoring rather than filtering: a reference may be an italic didone we do
    not have at exactly that contrast, and coming back with the nearest italic
    didone is right where coming back empty is not. Every trait is a
    preference, and the face that satisfies the most of them wins.
    """
    faces = available()
    if not faces:
        raise RuntimeError(f"no fonts bundled in {ASSET_DIR}")

    # Contrast alone cannot separate a slab from a grotesque - their measured
    # numbers overlap - so a bare contrast also implies a genre band. Without
    # this a flat geometric sans resolves to Roboto Slab, which is the right
    # number and the wrong shape.
    if genre is None and contrast is not None:
        genre = "sans" if contrast < 0.15 else "serif"

    def score(face: Face) -> float:
        points = 0.0
        # Contrast is the strongest signal we can actually measure, so it
        # carries the most weight: it is what separates a script from a
        # grotesque without anyone naming either.
        if contrast is not None:
            points += 3.0 * (1.0 - min(abs(face.contrast - contrast), 1.0))
        # A script has to be asked for. Its letters connect, so the glyph
        # filter finds few of them and its measured contrast is unreliable -
        # left to compete on that number alone a wedding script wins requests
        # for an editorial italic, which is a worse answer than any serif.
        if face.genre == "script" and genre != "script":
            points -= 2.0
        if italic is not None and face.italic == italic:
            points += 1.6
        if condensed is not None and face.condensed == condensed:
            points += 0.7
        if genre is not None and face.genre == genre:
            points += 1.4
        if category is not None and face.category == category:
            points += 1.0
        if exclude_family is not None and face.family == exclude_family:
            points -= 2.5
        # Penalised rather than excluded, so a request nothing meets still
        # returns the nearest face instead of nothing at all.
        if min_stroke is not None and face.stroke < min_stroke:
            points -= 5.0
        return points

    return max(faces, key=score)


def counterpart(face: Face) -> Face:
    """A face to stress a single word against `face`.

    Emphasis that a viewer registers comes from a change of voice - a serif
    against a sans, a script against a grotesque - not from the same face made
    bigger. So the counterpart always crosses genre.
    """
    wanted = {"sans": "serif", "display": "serif", "mono": "sans",
              "serif": "sans", "script": "sans"}[face.genre]
    # A script is the most characterful counterpart to flat sans body text,
    # which is exactly the move the reference in this repo makes.
    if face.genre in ("sans", "display") and face.contrast < 0.2:
        return choose(genre="script", contrast=0.7, italic=True, min_stroke=MIN_ACCENT_STROKE)
    return choose(genre=wanted, exclude_family=face.family, min_stroke=MIN_ACCENT_STROKE)


@functools.lru_cache(maxsize=None)
def resolve_font_path(category: str) -> pathlib.Path:
    """A usable font file for `category`, never raising.

    An unknown category degrades to the fallback: a caption in the wrong face
    is recoverable, a crashed render is not.
    """
    name = CATEGORY_FILES.get(category) or CATEGORY_FILES.get(FALLBACK_CATEGORY)
    if name and (ASSET_DIR / name).exists():
        return ASSET_DIR / name
    faces = available()
    if faces:
        return ASSET_DIR / faces[0].file
    existing = sorted(ASSET_DIR.glob("*.ttf"))
    if existing:
        return existing[0]
    raise RuntimeError(f"no fonts bundled in {ASSET_DIR}")


def _apply_weight(font: ImageFont.FreeTypeFont, weight: int) -> None:
    """Set the weight axis, leaving any other axis at its default.

    Handing `set_variation_by_axes` a single number works only for faces with
    exactly one axis. Several here carry an optical-size or width axis too, and
    the short list was silently rejected - so the heavy weight a caption needs
    never arrived and the type rendered at 400.
    """
    try:
        axes = font.get_variation_axes()
    except (OSError, AttributeError, ValueError):
        return      # a static face is already the weight it is
    if not axes:
        return
    values = []
    for axis in axes:
        name = axis.get("name") if isinstance(axis, dict) else None
        name = name.decode() if isinstance(name, bytes) else name
        default = axis.get("default", axis.get("minimum", 400)) if isinstance(axis, dict) else 400
        if name and "weight" in name.lower():
            low = axis.get("minimum", 100) if isinstance(axis, dict) else 100
            high = axis.get("maximum", 900) if isinstance(axis, dict) else 900
            values.append(float(max(low, min(high, weight))))
        else:
            values.append(float(default))
    try:
        font.set_variation_by_axes(values)
    except (OSError, AttributeError, ValueError):
        pass


@functools.lru_cache(maxsize=512)
def load_font(category: str, size: int, weight: int = DEFAULT_WEIGHT) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(resolve_font_path(category)), size)
    _apply_weight(font, weight)
    return font


@functools.lru_cache(maxsize=512)
def load_face(file: str, size: int, weight: int = DEFAULT_WEIGHT) -> ImageFont.FreeTypeFont:
    """Load one specific face, for callers that chose rather than categorised."""
    path = ASSET_DIR / file
    if not path.exists():
        return load_font(FALLBACK_CATEGORY, size, weight)
    font = ImageFont.truetype(str(path), size)
    _apply_weight(font, weight)
    return font


def weight_range(file: str) -> tuple[int, int] | None:
    """The weights a face can be set at, or None for a static face (one weight)."""
    try:
        axes = ImageFont.truetype(str(ASSET_DIR / file), 20).get_variation_axes()
    except (OSError, AttributeError, ValueError):
        return None
    for axis in axes or []:
        name = axis.get("name") if isinstance(axis, dict) else None
        name = name.decode() if isinstance(name, bytes) else name
        if name and "weight" in name.lower():
            return int(axis.get("minimum", 100)), int(axis.get("maximum", 900))
    return None


def catalogue() -> list[dict]:
    """Every shipped face, as a creator would choose from it."""
    out = []
    for face in available():
        weights = weight_range(face.file)
        out.append({"file": face.file, "family": face.family, "genre": face.genre,
                    "italic": face.italic, "caps_only": face.caps_only,
                    "weights": list(weights) if weights else None})
    return sorted(out, key=lambda f: (f["genre"], f["family"], f["italic"]))


if __name__ == "__main__":
    import json

    print(json.dumps(catalogue()))
