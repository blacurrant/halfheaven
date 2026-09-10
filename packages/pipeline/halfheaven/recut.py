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
import pathlib
import sys

from halfheaven.media.probe import probe
from halfheaven.plan.edits import CaptionEdit, apply_caption_edits, regroup_captions
from halfheaven.render.presets import apply_preset
from halfheaven.render.video import render
from halfheaven.schemas import EditProgram, StyleProfile


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
    program_path.write_text(program.model_dump_json(indent=2))
    print(f"      {len(program.captions)} cards remain")

    print(f"[{step + 1}/{steps}] rendering -> {args.out}")
    render(program, args.out, work_dir=pathlib.Path(args.work))
    print(f"done: {args.out}  ({probe(args.out).duration:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
