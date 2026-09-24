"""Re-render an existing edit after fixing its captions.

Deliberately does not touch the pipeline. Re-transcribing would discard the
correction that prompted the recut, and the analysis and editorial passes have
nothing new to say about a word the creator just retyped. Because the renderer
is a pure function of the program, this is only the render - seconds rather
than the whole job.
"""
from __future__ import annotations

import argparse
import json
import re
import pathlib
import sys

from halfheaven.media.probe import probe
from halfheaven.plan.edits import CaptionEdit, apply_caption_edits, regroup_captions
from halfheaven.render.presets import apply_preset
from halfheaven.plan.subject_captions import place_around_subject
from halfheaven.render.video import mask_track, render
from halfheaven.render.fonts import available
from halfheaven.schemas import CaptionProfile, EditProgram, StyleProfile

# What a creator may set on each kind of word. Anything else in a patch is
# dropped: this arrives from a browser.
TYPE_FIELDS = {"fill_hex", "size_pct", "font_file", "font_weight", "all_caps",
               "decor", "stroke_hex", "shadow_hex", "box_hex"}
# Type height as a share of frame height: below this it is unreadable on a
# phone, above it one word fills the screen.
MIN_SIZE, MAX_SIZE = 0.015, 0.2
# Which program style each side of the control edits.
TYPE_SIDES = {"body": ("captions", "default"), "pop": ("emphasis", "emphasis")}


def apply_type(profile: StyleProfile, program: EditProgram,
               patch: dict) -> tuple[StyleProfile, EditProgram]:
    """Merge a creator's type choices into both the profile and the program.

    Validated as a whole CaptionProfile, so an out-of-range size or a colour
    that is not a colour fails here, with a message, rather than in ffmpeg.
    """
    faces = {face.file for face in available()}
    styles = dict(program.styles)
    for side, changes in patch.items():
        if side not in TYPE_SIDES or not isinstance(changes, dict):
            raise ValueError(f"unknown side {side!r}; use body or pop")
        unknown = set(changes) - TYPE_FIELDS
        if unknown:
            raise ValueError(f"not a type setting: {', '.join(sorted(unknown))}")
        if "font_file" in changes and changes["font_file"] not in faces:
            raise ValueError(f"no such face: {changes['font_file']!r}")
        for field, value in changes.items():
            if field.endswith("_hex") and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(value)):
                raise ValueError(f"{field} wants #RRGGBB, not {value!r}")
        size = changes.get("size_pct")
        if size is not None and not (MIN_SIZE <= float(size) <= MAX_SIZE):
            raise ValueError(f"size {size} is outside {MIN_SIZE}-{MAX_SIZE} of frame height")
        weight = changes.get("font_weight")
        if weight is not None and not (100 <= int(weight) <= 1000):
            raise ValueError(f"weight {weight} is outside 100-1000")
        section, style = TYPE_SIDES[side]
        current = styles.get(style) or getattr(profile, section)
        updated = CaptionProfile.model_validate({**current.model_dump(), **changes})
        profile = profile.model_copy(update={section: updated})
        styles[style] = updated
    return profile, program.model_copy(update={"styles": styles})


def parse_edits(raw: str) -> list[CaptionEdit]:
    """Edits arrive as JSON from a UI, so unknown keys are dropped."""
    edits: list[CaptionEdit] = []
    for item in json.loads(raw or "[]"):
        if not isinstance(item, dict) or "index" not in item:
            continue
        emphasis = item.get("emphasis")
        edits.append(
            CaptionEdit(
                index=int(item["index"]),
                text=item.get("text"),
                emphasis=[int(i) for i in emphasis] if isinstance(emphasis, list) else None,
                delete=bool(item.get("delete")),
            )
        )
    return edits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-render an edit with corrected captions.")
    parser.add_argument("--program", required=True, help="edit_program.json from a finished job")
    parser.add_argument("--edits", default="[]", help="JSON list of caption edits")
    parser.add_argument("--out", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--preset", default="", help="switch the caption look")
    parser.add_argument("--music", default="", help="a bed to mix under the speech")
    parser.add_argument("--no-music", action="store_true", help="remove the bed")
    parser.add_argument("--subject-captions", choices=["off", "around", "behind"], default="",
                        help="how captions relate to the speaker")
    parser.add_argument("--type", default="",
                        help='JSON: {"body": {...}, "pop": {...}} caption type settings')
    parser.add_argument("--background", default="",
                        help='a "#RRGGBB" to put behind the speaker, or "none" for the original')
    args = parser.parse_args(argv)

    program_path = pathlib.Path(args.program)
    program = EditProgram.model_validate_json(program_path.read_text())
    edits = parse_edits(args.edits)

    steps = 2 + (1 if args.preset else 0)
    step = 1

    if args.preset:
        # A look only affects captions, so switching one is a restyle and a
        # render - the transcript and the cut are already decided.
        profile_path = program_path.parent / "style_profile.json"
        profile = (StyleProfile.model_validate_json(profile_path.read_text())
                   if profile_path.exists() else StyleProfile())
        profile = apply_preset(profile, args.preset)
        profile_path.write_text(profile.model_dump_json(indent=2))
        program = program.model_copy(update={
            "styles": {"default": profile.captions, "emphasis": profile.emphasis}})
        program = regroup_captions(program, profile.captions.max_words)
        print(f"[{step}/{steps}] look: {args.preset} "
              f"({profile.captions.font_category}, {profile.captions.max_words} words a card)")
        step += 1

    if args.type:
        # Type only changes how cards are drawn, so it is a restyle and a render.
        profile_path = program_path.parent / "style_profile.json"
        profile = (StyleProfile.model_validate_json(profile_path.read_text())
                   if profile_path.exists() else StyleProfile())
        try:
            profile, program = apply_type(profile, program, json.loads(args.type))
        except (ValueError, json.JSONDecodeError) as problem:
            print(f"type not applied: {problem}", file=sys.stderr)
            return 4
        profile_path.write_text(profile.model_dump_json(indent=2))
        print(f"      type: {', '.join(sorted(json.loads(args.type)))} restyled")

    if args.no_music:
        program = program.model_copy(update={"music": None})
        print("      music removed")
    elif args.music:
        # The bed is mixed in the finish pass, so adding one is a render rather
        # than a re-run - the cut and the transcript are already decided.
        from halfheaven.schemas import MusicBed
        existing = program.music
        program = program.model_copy(update={
            "music": MusicBed(src=args.music,
                              gain_db=existing.gain_db if existing else -16.0,
                              duck_db=existing.duck_db if existing else -9.0)})
        print(f"      music: {pathlib.Path(args.music).name}")

    print(f"[{step}/{steps}] applying {len(edits)} caption fix{'' if len(edits) == 1 else 'es'}")
    program = apply_caption_edits(program, edits)
    print(f"      {len(program.captions)} cards remain")

    # The speaker mode is re-applied after every change: a retyped or restyled
    # card is a different shape, and its old place may now sit on a face.
    profile_path = program_path.parent / "style_profile.json"
    profile = (StyleProfile.model_validate_json(profile_path.read_text())
               if profile_path.exists() else StyleProfile())
    if args.subject_captions:
        profile = profile.model_copy(update={"subject": profile.subject.model_copy(
            update={"captions": args.subject_captions})})
        profile_path.write_text(profile.model_dump_json(indent=2))
    if args.background:
        colour = None if args.background == "none" else args.background
        if colour is not None and not re.fullmatch(r"#[0-9A-Fa-f]{6}", colour):
            parser.error(f"--background wants #RRGGBB or none, not {colour!r}")
        profile = profile.model_copy(update={"subject": profile.subject.model_copy(
            update={"background_hex": colour})})
        profile_path.write_text(profile.model_dump_json(indent=2))
        program = program.model_copy(update={"look": program.look.model_copy(
            update={"background_hex": colour})})
        print(f"      background: {colour or 'as shot'}")
    mode = profile.subject.captions
    needs_subject = mode != "off" or program.look.background_hex is not None
    track = mask_track(program, "subject", args.work) if needs_subject else None
    if needs_subject and track is None:
        print("      this edit has no speaker separation; run it again to use it", file=sys.stderr)
        if args.subject_captions or (args.background and args.background != "none"):
            return 3
    program = place_around_subject(program, mode, track)
    if mode != "off":
        print(f"      captions {mode} the speaker: "
              f"{sum(c.home is not None for c in program.captions)} moved")
    program_path.write_text(program.model_dump_json(indent=2))

    print(f"[{step + 1}/{steps}] rendering -> {args.out}")
    render(program, args.out, work_dir=pathlib.Path(args.work))
    print(f"done: {args.out}  ({probe(args.out).duration:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
