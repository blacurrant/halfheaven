"""Builds persistent_title_over_three_shots.mp4.

Three visually distinct shots. Each shot has its own scenery text in its own
place; one title sits at the same position in every frame. Only the title
survives across the cuts, which is the property the detector must key on.
"""
import os
import pathlib
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 320, 568, 30
# Backgrounds differ strongly in both hue and luminance so the content
# detector actually registers the cuts.
SHOTS = [
    ((14, 16, 62), 30, "PLATFORM 6", (20, 40)),
    ((205, 200, 190), 60, "EXPRESS", (180, 460)),
    ((28, 118, 58), 45, None, None),
]
TITLE, TITLE_Y = "THREE DAYS", 400

_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def font(size):
    for path in _FONTS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main():
    here = pathlib.Path(__file__).parent
    small, big = font(22), font(40)
    with tempfile.TemporaryDirectory() as tmp:
        index = 0
        for bg, frames, text, position in SHOTS:
            for _ in range(frames):
                image = Image.new("RGB", (W, H), bg)
                draw = ImageDraw.Draw(image)
                # structure so the gradient detector has real edges to find
                for i in range(6):
                    x = 12 + i * 50
                    shade = tuple(max(0, min(255, c + (60 if sum(bg) < 300 else -70))) for c in bg)
                    draw.rectangle([x, 120, x + 38, 300], fill=shade)
                if text:
                    draw.text(position, text, font=small, fill=(255, 255, 255),
                              stroke_width=4, stroke_fill=(0, 0, 0))
                # scenery text above is per-shot; the title below is constant
                box = draw.textbbox((0, 0), TITLE, font=big)
                draw.text(((W - (box[2] - box[0])) // 2, TITLE_Y), TITLE, font=big,
                          fill=(255, 233, 74), stroke_width=6, stroke_fill=(0, 0, 0))
                image.save(f"{tmp}/{index:05d}.png")
                index += 1
        subprocess.run(
            [os.environ.get("FFMPEG", "ffmpeg"), "-v", "error", "-y",
             "-framerate", str(FPS), "-i", f"{tmp}/%05d.png",
             "-pix_fmt", "yuv420p", str(here / "persistent_title_over_three_shots.mp4")],
            check=True,
        )


if __name__ == "__main__":
    main()
