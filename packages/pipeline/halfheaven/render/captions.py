"""Caption cards drawn with Pillow and composited as RGBA overlays.

Chosen over ffmpeg's drawtext because drawtext cannot mix typefaces within a
line or reveal words one at a time, it depends on how ffmpeg was compiled (the
build here has neither drawtext nor libass), and a Pillow card can be asserted
on pixel by pixel in a test.

A card is a list of styled runs. Runs name entries in the program's style
table, which is what lets one line carry a monospace body and a large serif
emphasis at once.
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

from halfheaven.render.fonts import load_font
from halfheaven.schemas import Canvas, CaptionProfile, TextRun

SIDE_MARGIN_PCT = 0.06
LINE_SPACING = 1.18
HEAVY_STROKE_RATIO = 0.10
# A caption composited over arbitrary footage always needs edge separation, even
# when the reference had none - the reference's captions sat on a letterbox bar.
# Legibility is a floor, not a style choice.
MIN_STROKE_RATIO = 0.035

_DEFAULT_PROFILE = CaptionProfile(present=True)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


class _Token:
    """One drawable word, carrying the style it was written in."""

    __slots__ = ("text", "profile", "font", "size", "width", "stroke")

    def __init__(self, text: str, profile: CaptionProfile, canvas: Canvas) -> None:
        self.text = text
        self.profile = profile
        self._resize(max(8, int(canvas.height * profile.size_pct)))

    def _resize(self, size: int) -> None:
        self.size = max(8, size)
        self.font: ImageFont.FreeTypeFont = load_font(self.profile.font_category, self.size)
        ratio = HEAVY_STROKE_RATIO if self.profile.stroke_heavy else MIN_STROKE_RATIO
        self.stroke = max(1, int(self.size * ratio))
        self.width = self.font.getlength(self.text)

    def fit_within(self, max_width: float) -> None:
        """Shrink until the word fits.

        A single word cannot wrap, so an emphasis face large enough to overflow
        gets clipped at the frame edge - and Pillow clips silently, which is how
        this shipped once already.
        """
        if self.width <= max_width or self.width <= 0:
            return
        self._resize(int(self.size * max_width / self.width))
        while self.width > max_width and self.size > 8:
            self._resize(self.size - 1)


def _tokenise(runs: list[TextRun], canvas: Canvas, styles: dict[str, CaptionProfile]) -> list[_Token]:
    tokens: list[_Token] = []
    for run in runs:
        profile = styles.get(run.style) or _DEFAULT_PROFILE
        text = run.text.upper() if profile.all_caps else run.text
        for word in text.split():
            tokens.append(_Token(word, profile, canvas))
    return tokens


def _wrap(tokens: list[_Token], max_width: float, space: float) -> list[list[_Token]]:
    lines: list[list[_Token]] = []
    current: list[_Token] = []
    width = 0.0
    for token in tokens:
        needed = token.width + (space if current else 0.0)
        if current and width + needed > max_width:
            lines.append(current)
            current, width = [token], token.width
        else:
            current.append(token)
            width += needed
    if current:
        lines.append(current)
    return lines


def render_caption(
    runs: list[TextRun],
    canvas: Canvas,
    styles: dict[str, CaptionProfile],
    out_path: str | pathlib.Path,
) -> pathlib.Path:
    """Draw one caption card, transparent everywhere except the text."""
    out_path = pathlib.Path(out_path)
    image = Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0))
    tokens = _tokenise(runs, canvas, styles)

    if tokens:
        draw = ImageDraw.Draw(image)
        max_width = canvas.width * (1 - 2 * SIDE_MARGIN_PCT)
        for token in tokens:
            token.fit_within(max_width)
        space = max(t.font.getlength(" ") for t in tokens)
        lines = _wrap(tokens, max_width, space)

        # Position from the largest run: for a single-word emphasis card that is
        # the word itself, and for a mixed line it is the part the eye lands on.
        dominant = max(tokens, key=lambda t: t.size).profile
        line_heights = [max(t.size for t in line) * LINE_SPACING for line in lines]
        block_height = sum(line_heights)
        centre_x = canvas.width * dominant.anchor[0]
        # Keep the whole block on screen: a tall emphasis line can push an
        # anchored block past the bottom edge.
        margin = canvas.height * SIDE_MARGIN_PCT
        top = canvas.height * dominant.anchor[1] - block_height / 2
        top = max(margin, min(top, canvas.height - block_height - margin))

        for line, height in zip(lines, line_heights):
            line_width = sum(t.width for t in line) + space * (len(line) - 1)
            x = centre_x - line_width / 2
            baseline = top + height
            for token in line:
                # align on the baseline so mixed sizes sit on one line
                y = baseline - token.size * LINE_SPACING
                draw.text(
                    (x, y), token.text, font=token.font,
                    fill=(*_hex_to_rgb(token.profile.fill_hex), 255),
                    stroke_width=token.stroke,
                    stroke_fill=(*_hex_to_rgb(token.profile.stroke_hex), 255),
                )
                x += token.width + space
            top += height

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    return out_path


def build_caption_track(program, work_dir: str | pathlib.Path) -> pathlib.Path:
    """Write an ffmpeg concat list describing the whole caption track.

    Captions never overlap, so the track is one timeline of still cards
    separated by transparent gaps. Rendering it as a single input rather than
    one input per caption is what keeps memory constant.

    A card whose runs all carry times is expanded into one still per word, each
    showing one more word than the last. Word-by-word reveal therefore costs
    nothing structurally - it is simply more entries in the same list.
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
        start = max(cursor, caption.t)
        if start - cursor > 1e-4:
            spans.append((blank, start - cursor))
        end = min(program.duration, start + caption.duration)
        if end <= start:
            continue

        if caption.reveals_word_by_word:
            times = sorted({run.t for run in caption.runs if run.t is not None})
            for order, moment in enumerate(times):
                state_start = max(start, moment)
                state_end = times[order + 1] if order + 1 < len(times) else end
                state_end = min(end, state_end)
                if state_end <= state_start:
                    continue
                visible = [r for r in caption.runs if r.t is not None and r.t <= moment]
                card = render_caption(
                    visible, canvas, styles, work_dir / f"caption_{index:04d}_{order:02d}.png"
                )
                spans.append((card, state_end - state_start))
        else:
            card = render_caption(
                caption.runs, canvas, styles, work_dir / f"caption_{index:04d}_00.png"
            )
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
