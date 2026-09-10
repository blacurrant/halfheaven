"""Caption cards drawn with Pillow and composited as RGBA overlays.

Chosen over ffmpeg's drawtext because drawtext cannot mix typefaces in a line,
mark the word being spoken, or reveal words one at a time; it also depends on
how ffmpeg was compiled (the build here has neither drawtext nor libass). A
Pillow card can additionally be asserted on pixel by pixel in a test.

Style is expressed as independent axes - grouping, reveal, enter, active
treatment, decoration, layout - so the looks creators name are combinations
rather than separate code paths.
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from halfheaven.render.caption_frames import CaptionFrame, frames_for
from halfheaven.render.fonts import load_font
from halfheaven.schemas import Canvas, CaptionProfile, TextRun

SIDE_MARGIN_PCT = 0.06
LINE_SPACING = 1.18
HEAVY_STROKE_RATIO = 0.10
# A caption over arbitrary footage always needs edge separation, even when the
# reference had none - its captions sat on a letterbox bar. Legibility is a
# floor, not a style choice.
MIN_STROKE_RATIO = 0.035

_DEFAULT = CaptionProfile(present=True)


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _ease_out(t: float) -> float:
    return 1 - (1 - max(0.0, min(1.0, t))) ** 3


class _Token:
    """One drawable word, at the size and in the face its own run asks for."""

    __slots__ = ("text", "font", "size", "width", "height", "is_active", "style")

    def __init__(self, text: str, profile: CaptionProfile, canvas: Canvas,
                 factor: float, is_active: bool) -> None:
        self.text = text
        self.is_active = is_active
        self.style = profile
        base = max(8, int(canvas.height * profile.size_pct))
        self.size = max(6, int(base * factor))
        self.font: ImageFont.FreeTypeFont = load_font(
            profile.font_category, self.size, profile.font_weight)
        self.width = self.font.getlength(text)
        self.height = self.size

    def fit(self, max_width: float) -> None:
        """A single word cannot wrap, so an oversized one shrinks.

        Pillow clips silently at the image edge, which is how a clipped caption
        once shipped looking merely 'cropped'.
        """
        if self.width <= max_width or self.width <= 0:
            return
        self.size = max(6, int(self.size * max_width / self.width))
        self.font = load_font(self.style.font_category, self.size, self.style.font_weight)
        self.width = self.font.getlength(self.text)
        self.height = self.size


def _tokens(frame: CaptionFrame, canvas: Canvas, profile: CaptionProfile,
            styles: dict[str, CaptionProfile] | None = None) -> list[_Token]:
    out: list[_Token] = []
    for index, run in enumerate(frame.shown):
        # a run names its own style; the card's profile is the fallback, which
        # is what lets one line carry a mono body and a Didone punch
        own = (styles or {}).get(run.style) or profile
        text = run.text.upper() if own.all_caps else run.text
        factor = 1.0
        if frame.entering == index and profile.enter == "pop":
            factor = profile.pop_from + (1 - profile.pop_from) * _ease_out(frame.progress)
        if frame.active == index and profile.active == "scale":
            factor *= profile.active_scale
        # A run is normally one word, but nothing requires it: a run holding a
        # phrase must still wrap word by word rather than shrink to fit as one
        # very long token.
        for word in text.split() or [""]:
            if word:
                out.append(_Token(word, own, canvas, factor, frame.active == index))
    return out


def _lines(tokens: list[_Token], profile: CaptionProfile, max_width: float,
           space: float) -> list[list[_Token]]:
    if profile.layout == "stack":
        return [[t] for t in tokens]
    lines: list[list[_Token]] = []
    current: list[_Token] = []
    width = 0.0
    for token in tokens:
        need = token.width + (space if current else 0)
        if current and width + need > max_width:
            lines.append(current)
            current, width = [token], token.width
        else:
            current.append(token)
            width += need
    if current:
        lines.append(current)
    return lines


def render_frame(frame: CaptionFrame, canvas: Canvas, profile: CaptionProfile,
                 out_path: str | pathlib.Path,
                 styles: dict[str, CaptionProfile] | None = None) -> pathlib.Path:
    """Draw one caption still, transparent everywhere except the card."""
    out_path = pathlib.Path(out_path)
    image = Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0))
    tokens = _tokens(frame, canvas, profile, styles)

    if tokens:
        draw = ImageDraw.Draw(image)
        max_width = canvas.width * (1 - 2 * SIDE_MARGIN_PCT)
        for token in tokens:
            token.fit(max_width)
        space = max(t.font.getlength(" ") for t in tokens)
        lines = _lines(tokens, profile, max_width, space)

        heights = [max(t.height for t in line) * LINE_SPACING for line in lines]
        block = sum(heights)
        widths = [sum(t.width for t in line) + space * (len(line) - 1) for line in lines]
        centre_x = canvas.width * profile.anchor[0]
        margin = canvas.height * SIDE_MARGIN_PCT
        top = canvas.height * profile.anchor[1] - block / 2
        top = max(margin, min(top, canvas.height - block - margin))

        pad = max(6, int(tokens[0].size * 0.28))
        radius = int(tokens[0].size * profile.box_radius_pct * 2)

        # a single panel behind the whole card
        if profile.decor == "box":
            widest = max(widths)
            draw.rounded_rectangle(
                [centre_x - widest / 2 - pad, top - pad * 0.7,
                 centre_x + widest / 2 + pad, top + block + pad * 0.7],
                radius=radius, fill=(*_rgb(profile.box_hex), int(255 * profile.box_alpha)))

        # place every glyph, painting per-word backing as we go
        placements: list[tuple[_Token, float, float]] = []
        y = top
        for line, height, width in zip(lines, heights, widths):
            x = centre_x - width / 2
            for token in line:
                baseline = y + height - token.height * LINE_SPACING
                placements.append((token, x, baseline))
                x += token.width + space
            y += height

        for token, x, baseline in placements:
            if profile.decor == "pill":
                draw.rounded_rectangle(
                    [x - pad * 0.5, baseline - pad * 0.25,
                     x + token.width + pad * 0.5, baseline + token.height + pad * 0.35],
                    radius=radius,
                    fill=(*_rgb(profile.box_hex), int(255 * profile.box_alpha)))
            if token.is_active and profile.active == "marker":
                draw.rounded_rectangle(
                    [x - pad * 0.35, baseline + token.height * 0.12,
                     x + token.width + pad * 0.35, baseline + token.height * 1.05],
                    radius=int(token.size * 0.12), fill=(*_rgb(profile.active_box_hex), 255))

        # hard shadow sits under the glyphs; soft shadow is the same, blurred
        if profile.decor in ("shadow_hard", "shadow_soft"):
            layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            shade = ImageDraw.Draw(layer)
            for token, x, baseline in placements:
                offset = token.size * profile.shadow_offset_pct
                shade.text((x + offset, baseline + offset), token.text, font=token.font,
                           fill=(*_rgb(profile.shadow_hex), 235))
            if profile.decor == "shadow_soft":
                layer = layer.filter(ImageFilter.GaussianBlur(max(2, tokens[0].size * 0.08)))
            image.alpha_composite(layer)
            draw = ImageDraw.Draw(image)

        for token, x, baseline in placements:
            own = token.style
            stroke = 0
            if own.decor == "stroke":
                ratio = HEAVY_STROKE_RATIO if own.stroke_heavy else MIN_STROKE_RATIO
                stroke = max(1, int(token.size * ratio))
            fill = own.active_fill_hex if (token.is_active and own.active == "colour") else own.fill_hex
            draw.text((x, baseline), token.text, font=token.font, fill=(*_rgb(fill), 255),
                      stroke_width=stroke, stroke_fill=(*_rgb(own.stroke_hex), 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    return out_path


def render_card(frame: CaptionFrame, canvas: Canvas, styles: dict[str, CaptionProfile],
                out_path: str | pathlib.Path) -> pathlib.Path:
    """One still, with every run drawn in the style it names."""
    profile = styles.get("default") or _DEFAULT
    return render_frame(frame, canvas, profile, out_path, styles)


def render_caption(runs: list[TextRun], canvas: Canvas, styles: dict[str, CaptionProfile],
                   out_path: str | pathlib.Path) -> pathlib.Path:
    """A whole card at rest."""
    profile = styles.get(runs[0].style if runs else "default") or _DEFAULT
    return render_frame(CaptionFrame(runs=list(runs), duration=0.0), canvas, profile,
                        out_path, styles)


def build_caption_track(program, work_dir: str | pathlib.Path) -> pathlib.Path:
    """Write an ffmpeg concat list describing the whole caption track.

    Captions never overlap, so the track is one timeline of stills separated by
    transparent gaps. Rendering it as a single input rather than one input per
    caption is what keeps memory constant.
    """
    # Absolute, because the concat demuxer resolves 'file' entries relative to
    # the list file's own directory - a relative work dir would double up.
    work_dir = pathlib.Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    canvas = program.canvas
    styles = program.styles or {}

    blank = work_dir / "blank_card.png"
    if not blank.exists():
        Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0)).save(blank)

    spans: list[tuple[pathlib.Path, float]] = []
    cursor = 0.0
    for index, caption in enumerate(sorted(program.captions, key=lambda c: c.t)):
        profile = styles.get(caption.style) or _DEFAULT
        start = max(cursor, caption.t)
        if start - cursor > 1e-4:
            spans.append((blank, start - cursor))
        frames = frames_for(caption, profile, program.duration)
        if not frames:
            continue
        for order, frame in enumerate(frames):
            card = render_frame(frame, canvas, profile,
                                work_dir / f"cap_{index:04d}_{order:03d}.png", styles)
            spans.append((card, frame.duration))
        cursor = min(program.duration, start + caption.duration)

    if program.duration - cursor > 1e-4:
        spans.append((blank, program.duration - cursor))
    if not spans:
        spans.append((blank, program.duration))

    lines = ["# caption track"]
    for path, duration in spans:
        lines.append(f"file '{path}'")
        lines.append(f"duration {duration:.4f}")
    # The concat demuxer drops the final entry's duration unless the file is
    # repeated, which would truncate the last caption.
    lines.append(f"file '{spans[-1][0]}'")

    listing = work_dir / "caption_track.txt"
    listing.write_text("\n".join(lines) + "\n")
    return listing
