"""Caption cards drawn with Pillow and composited as RGBA overlays.

Chosen over ffmpeg's drawtext for three reasons: drawtext cannot do per-word
highlighting or animation, it depends on how ffmpeg was compiled (the build on
this machine has no drawtext or libass at all), and a Pillow card can be
asserted on pixel by pixel in a test.
"""
from __future__ import annotations

import os
import pathlib

from PIL import Image, ImageDraw, ImageFont

from halfheaven.schemas import Canvas, CaptionProfile

# Fonts we are entitled to embed. Style matching picks the nearest of these
# rather than reproducing a font we have no licence for.
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)

SIDE_MARGIN_PCT = 0.06
LINE_SPACING = 1.15
HEAVY_STROKE_RATIO = 0.10
# A caption composited over arbitrary footage always needs edge separation, even
# when the reference had none - the reference's captions sat on a letterbox bar.
# Legibility is a floor, not a style choice.
MIN_STROKE_RATIO = 0.035


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Greedy wrap on word boundaries so a caption never leaves the frame."""
    lines: list[str] = []
    current: list[str] = []
    for word in text.split():
        candidate = " ".join(current + [word])
        box = draw.textbbox((0, 0), candidate, font=font)
        if current and box[2] - box[0] > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def render_caption(
    text: str,
    canvas: Canvas,
    profile: CaptionProfile,
    out_path: str | pathlib.Path,
) -> pathlib.Path:
    """Draw one caption card, transparent everywhere except the text."""
    out_path = pathlib.Path(out_path)
    image = Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0))

    if text.strip():
        draw = ImageDraw.Draw(image)
        if profile.all_caps:
            text = text.upper()

        size = max(8, int(canvas.height * profile.size_pct))
        font = _load_font(size)
        ratio = HEAVY_STROKE_RATIO if profile.stroke_heavy else MIN_STROKE_RATIO
        stroke = max(1, int(size * ratio))
        max_width = int(canvas.width * (1 - 2 * SIDE_MARGIN_PCT))

        lines = _wrap(text, font, max_width, draw)
        line_height = int(size * LINE_SPACING)
        block_height = line_height * len(lines)

        centre_x = canvas.width * profile.anchor[0]
        top = canvas.height * profile.anchor[1] - block_height / 2

        fill = _hex_to_rgb(profile.fill_hex)
        stroke_fill = _hex_to_rgb(profile.stroke_hex)
        for index, line in enumerate(lines):
            box = draw.textbbox((0, 0), line, font=font)
            x = centre_x - (box[2] - box[0]) / 2
            y = top + index * line_height
            draw.text(
                (x, y), line, font=font, fill=(*fill, 255),
                stroke_width=stroke, stroke_fill=(*stroke_fill, 255),
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    return out_path
