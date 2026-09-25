"""Stills of every caption look, drawn on the creator's own edit.

The studio shows these before a look is chosen, so they have to be the real
thing: the same card at the same moment, through the same regrouping, frame
expansion and renderer a recut would use, over a frame of the edit itself. A
browser imitation would disagree with the render the moment a look reveals
word by word or changes face.

    python -m halfheaven.previews --program edit_program.json --work DIR --out-dir DIR
prints a JSON list of {"id", "label", "blurb", "file"}.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

from PIL import Image

from halfheaven.media.ffmpeg_bin import ffmpeg
from halfheaven.plan.edits import regroup_captions
from halfheaven.recut import MATCHED, matched_look
from halfheaven.render.caption_frames import CaptionFrame, frames_for
from halfheaven.render.captions import render_frame
from halfheaven.render.presets import CAPTION_PRESETS, apply_preset
from halfheaven.schemas import Caption, EditProgram, StyleProfile

# Wide enough to read a caption on a phone, small enough that eight load at once.
WIDTH = 270
MATCHED_LABEL = ("Matched", "The captions measured from your reel")


def moment(program: EditProgram) -> float | None:
    """A time worth showing: inside a card of a few words, ideally a stressed
    one, near the middle of the edit."""
    cards = [c for c in program.captions if c.runs]
    if not cards:
        return None
    middle = program.duration / 2

    def rank(card: Caption) -> tuple[int, int, float]:
        stressed = any(run.style == "emphasis" for run in card.runs)
        return (0 if 2 <= len(card.runs) <= 5 else 1, 0 if stressed else 1, abs(card.t - middle))

    card = min(cards, key=rank)
    return card.t + card.duration * 0.6


def frame_at(program: EditProgram, at: float) -> tuple[Caption, CaptionFrame] | None:
    """The card on screen at `at`, and exactly how it is drawn then."""
    cards = sorted((c for c in program.captions if c.runs), key=lambda c: c.t)
    showing = [c for c in cards if c.t <= at]
    if not showing:
        return None
    card = showing[-1]
    profile = (program.styles or {}).get(card.style)
    if profile is None:
        return None
    frames = frames_for(card, profile, program.duration)
    if not frames:
        return None
    clock = card.t
    for frame in frames:
        if clock + frame.duration > at:
            return card, frame
        clock += frame.duration
    return card, frames[-1]


def wearing(program: EditProgram, profile: StyleProfile, look: str,
            program_path: pathlib.Path) -> EditProgram:
    """`program` as a recut with --preset `look` would leave it."""
    styled = (matched_look(profile, program_path) if look == MATCHED
              else apply_preset(profile, look))
    program = program.model_copy(update={
        "styles": {"default": styled.captions, "emphasis": styled.emphasis}})
    return regroup_captions(program, styled.captions.max_words)


def background(video: pathlib.Path, at: float, lut: str | None, out: pathlib.Path) -> Image.Image:
    """The edit's picture at `at`, graded as the finished render grades it."""
    graded = ["-vf", f"lut3d=file='{lut}':interp=tetrahedral"] if lut and pathlib.Path(lut).exists() else []
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-ss", f"{max(0.0, at):.3f}", "-i", str(video),
                    *graded, "-frames:v", "1", str(out)], check=True, capture_output=True)
    return Image.open(out).convert("RGBA")


def render_previews(program_path: pathlib.Path, work: pathlib.Path, out_dir: pathlib.Path,
                    base: pathlib.Path | None = None, width: int = WIDTH) -> list[dict[str, str]]:
    program = EditProgram.model_validate_json(program_path.read_text())
    profile_path = program_path.parent / "style_profile.json"
    profile = (StyleProfile.model_validate_json(profile_path.read_text())
               if profile_path.exists() else StyleProfile())
    at = moment(program)
    if at is None:
        return []

    # base.mp4 is the cut before captions; the finished file would show the
    # current look's captions underneath every other look.
    base = base or next((p for p in (work / "base.mp4", work / "out.mp4") if p.exists()), None)
    if base is None:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    canvas = program.canvas
    height = round(width * canvas.height / canvas.width)

    looks: list[tuple[str, str, str]] = []
    if (program_path.parent / "style_profile.matched.json").exists():
        looks.append((MATCHED, *MATCHED_LABEL))
    looks += [(key, str(value["label"]), str(value["blurb"])) for key, value in CAPTION_PRESETS.items()]

    made: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory() as scratch:
        scratch_dir = pathlib.Path(scratch)
        picture = background(base, at, program.look.lut, scratch_dir / "frame.png")
        picture = picture.resize((canvas.width, canvas.height))
        for key, label, blurb in looks:
            dressed = wearing(program, profile, key, program_path)
            found = frame_at(dressed, at)
            still = picture.copy()
            if found:
                card, frame = found
                styles = dressed.styles or {}
                layer = render_frame(frame, canvas, styles.get(card.style), scratch_dir / f"{key}.png",
                                     styles, anchor=card.anchor)
                still.alpha_composite(Image.open(layer).convert("RGBA"))
            path = out_dir / f"{key}.jpg"
            still.convert("RGB").resize((width, height), Image.LANCZOS).save(path, quality=84)
            made.append({"id": key, "label": label, "blurb": blurb, "file": path.name})
    return made


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draw every caption look on an edit.")
    parser.add_argument("--program", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--base", default="", help="the uncaptioned cut; defaults to WORK/base.mp4")
    parser.add_argument("--width", type=int, default=WIDTH)
    args = parser.parse_args(argv)
    made = render_previews(pathlib.Path(args.program), pathlib.Path(args.work),
                           pathlib.Path(args.out_dir),
                           pathlib.Path(args.base) if args.base else None, args.width)
    print(json.dumps(made))
    return 0


if __name__ == "__main__":
    sys.exit(main())
