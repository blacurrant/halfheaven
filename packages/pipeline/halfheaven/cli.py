"""End-to-end: reference + target -> edited MP4.

Deliberately thin. Every decision lives in an analysed, planned or rendered
stage that can be tested on its own; this only wires them together and reports
what each stage decided.
"""
from __future__ import annotations

import argparse
import dataclasses
import pathlib
import sys

from halfheaven.analyze.reference import build_style_profile
from halfheaven.groq.client import GroqClient
from halfheaven.media.audio import extract_audio
from halfheaven.media.probe import probe
from halfheaven.plan.builder import build_program
from halfheaven.plan.chunking import chunk_captions
from halfheaven.plan.editor import decide
from halfheaven.render.video import render
from halfheaven.schemas import Canvas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply one video's edit style to another.")
    parser.add_argument("--reference", required=True, help="an edited video to copy the style of")
    parser.add_argument("--target", required=True, help="the footage to apply that style to")
    parser.add_argument("--out", default="out.mp4")
    parser.add_argument("--work", default="work")
    args = parser.parse_args(argv)

    work = pathlib.Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    client = GroqClient()
    client.verify_models()

    print(f"[1/5] analysing reference {args.reference}")
    profile = build_style_profile(args.reference, client=client, work_dir=work)
    print(f"      kind={profile.kind}  median shot={profile.pacing.median_shot:.2f}s  "
          f"cuts/min={profile.pacing.cuts_per_min:.1f}")
    if profile.captions.present:
        print(f"      captions at {profile.captions.anchor} fill={profile.captions.fill_hex} "
              f"max_words={profile.captions.max_words}")
    (work / "style_profile.json").write_text(profile.model_dump_json(indent=2))

    print(f"[2/5] transcribing target {args.target}")
    target_info = probe(args.target)
    if not target_info.has_audio:
        print("      target has no audio track - the speech engine needs one", file=sys.stderr)
        return 2
    transcript = client.transcribe(extract_audio(args.target, work / "target.wav"))
    print(f"      {len(transcript.words)} words over {transcript.duration:.1f}s")

    print("[3/5] editorial pass")
    decisions = decide(client, transcript, profile)
    decisions = dataclasses.replace(
        decisions,
        caption_chunks=chunk_captions(
            transcript.words,
            cuts=decisions.cuts,
            max_words=profile.captions.max_words,
            emphasis_indices=decisions.punch_word_indices,
            min_words=3,
        ),
    )
    removed = sum(stop - start for start, stop in decisions.cuts)
    print(f"      {len(decisions.cuts)} cuts removing {removed} words, "
          f"{len(decisions.caption_chunks)} caption cards, "
          f"{len(decisions.punch_word_indices)} punch-ins")

    print("[4/5] building program")
    program = build_program(
        source=str(args.target),
        canvas=Canvas(width=target_info.width, height=target_info.height, fps=target_info.fps),
        transcript=transcript,
        profile=profile,
        decisions=decisions,
    )
    program = program.model_copy(update={"styles": {"default": profile.captions}})
    (work / "edit_program.json").write_text(program.model_dump_json(indent=2))
    print(f"      {len(program.video)} clips, {program.duration:.1f}s "
          f"(from {target_info.duration:.1f}s), {len(program.captions)} captions")

    print(f"[5/5] rendering -> {args.out}")
    render(program, args.out, work_dir=work)
    print(f"done: {args.out}  ({probe(args.out).duration:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
