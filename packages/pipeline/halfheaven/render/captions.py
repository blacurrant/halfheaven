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


def build_caption_track(program, work_dir: str | pathlib.Path) -> pathlib.Path:
    """Write an ffmpeg concat list describing the whole caption track.

    Captions never overlap, so the entire track is one timeline of still cards
    separated by transparent gaps. Rendering them as one input instead of one
    input per caption is what keeps memory constant: the previous design held a
    full-size RGBA still open for every caption and got the process killed.
    """
    # Absolute, because the concat demuxer resolves 'file' entries relative to
    # the list file's own directory - a relative work dir would double up.
    work_dir = pathlib.Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    canvas = program.canvas

    blank = work_dir / "blank_card.png"
    if not blank.exists():
        Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0)).save(blank)

    spans: list[tuple[pathlib.Path, float]] = []
    cursor = 0.0
    for index, caption in enumerate(sorted(program.captions, key=lambda c: c.t)):
        start = max(cursor, caption.t)
        if start - cursor > 1e-4:
            spans.append((blank, start - cursor))
        style = program.styles.get(caption.style) or CaptionProfile(present=True)
        card = render_caption(caption.text, canvas, style, work_dir / f"caption_{index:04d}.png")
        end = min(program.duration, start + caption.duration)
        if end > start:
            spans.append((card, end - start))
            cursor = end

    if program.duration - cursor > 1e-4:
        spans.append((blank, program.duration - cursor))
    if not spans:
        spans.append((blank, program.duration))

    lines: list[str] = ["# caption track"]
    for path, duration in spans:
        lines.append(f"file '{path}'")
        lines.append(f"duration {duration:.4f}")
    # The concat demuxer drops the final entry's duration unless the file is
    # repeated, which would truncate the last caption.
    lines.append(f"file '{spans[-1][0]}'")

    listing = work_dir / "caption_track.txt"
    listing.write_text("\n".join(lines) + "\n")
    return listing
