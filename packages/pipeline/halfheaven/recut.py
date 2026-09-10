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
from halfheaven.plan.edits import CaptionEdit, apply_caption_edits
from halfheaven.render.video import render
from halfheaven.schemas import EditProgram


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
    args = parser.parse_args(argv)

    program_path = pathlib.Path(args.program)
    program = EditProgram.model_validate_json(program_path.read_text())
    edits = parse_edits(args.edits)

    print(f"[1/2] applying {len(edits)} caption fix{'' if len(edits) == 1 else 'es'}")
    program = apply_caption_edits(program, edits)
    program_path.write_text(program.model_dump_json(indent=2))
    print(f"      {len(program.captions)} cards remain")

    print(f"[2/2] rendering -> {args.out}")
    render(program, args.out, work_dir=pathlib.Path(args.work))
    print(f"done: {args.out}  ({probe(args.out).duration:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
