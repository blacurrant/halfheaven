"""Builds wide_subject_moves.mp4: a 16:9 source whose subject is not centred.

Centre-cropping a wide source to vertical throws away most of the frame, so if
the speaker stands off to one side they simply vanish. This fixture moves the
subject left, centre, then right so a tracker has something to follow and a
centre crop is demonstrably wrong.
"""
import os
import pathlib
import subprocess
import tempfile

from PIL import Image, ImageDraw

W, H, FPS = 640, 360, 25
# (x centre as a fraction of width, frames)
MOVES = [(0.22, 40), (0.5, 30), (0.8, 40)]


def main():
    here = pathlib.Path(__file__).parent
    with tempfile.TemporaryDirectory() as tmp:
        index = 0
        for centre, frames in MOVES:
            for _ in range(frames):
                image = Image.new("RGB", (W, H), (26, 28, 34))
                draw = ImageDraw.Draw(image)
                for k in range(8):  # static background structure
                    x = 10 + k * 80
                    draw.rectangle([x, 40, x + 46, 300], fill=(52, 54, 62))
                cx = int(W * centre)
                draw.ellipse([cx - 52, 120, cx + 52, 330], fill=(228, 196, 172))
                image.save(f"{tmp}/{index:05d}.png")
                index += 1
        subprocess.run(
            [os.environ.get("FFMPEG", "ffmpeg"), "-v", "error", "-y",
             "-framerate", str(FPS), "-i", f"{tmp}/%05d.png",
             "-pix_fmt", "yuv420p", str(here / "wide_subject_moves.mp4")],
            check=True,
        )


if __name__ == "__main__":
    main()
