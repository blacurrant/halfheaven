import pathlib

import pytest
from PIL import Image, ImageDraw, ImageFont

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int):
    for path in _FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


@pytest.fixture
def caption_frame(tmp_path):
    """A 1080x1920 frame with a caption whose position and colour we know exactly.

    Ground truth: text centre at x=0.50, y~0.74; fill #FFE94A; cap height 72px
    Text is sized to fit within the frame so centring is not satisfied trivially.
    """

    def build(text="CHANGES EVERYTHING", y_pct=0.72, fill=(255, 233, 74), distractor=False):
        width, height = 1080, 1920
        image = Image.new("RGB", (width, height), (28, 26, 34))
        draw = ImageDraw.Draw(image)
        if distractor:
            draw.ellipse([240, 420, 840, 1120], fill=(74, 64, 92))
        font = _font(72)
        box = draw.textbbox((0, 0), text, font=font)
        x = (width - (box[2] - box[0])) // 2
        y = int(height * y_pct)
        draw.text((x, y), text, font=font, fill=fill, stroke_width=10, stroke_fill=(0, 0, 0))
        path = tmp_path / "frame.png"
        image.save(path)
        return path

    return build


@pytest.fixture
def blank_frame(tmp_path):
    def build():
        path = tmp_path / "blank.png"
        Image.new("RGB", (1080, 1920), (28, 26, 34)).save(path)
        return path

    return build
