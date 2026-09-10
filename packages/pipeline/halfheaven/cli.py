"""End-to-end: reference + target -> edited MP4.

Deliberately thin. Every decision lives in an analysed, planned or rendered
stage that can be tested on its own; this only wires them together and reports
what each stage decided.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys

from halfheaven.analyze.reference import build_style_profile
from halfheaven.analyze.subject import needs_reframe, track_subject
from halfheaven.groq.asr import Transcript
from halfheaven.groq.client import GroqClient
from halfheaven.media.audio import extract_audio
from halfheaven.media.probe import probe
from halfheaven.plan.builder import build_program
from halfheaven.plan.chunking import chunk_captions
from halfheaven.plan.editor import decide
from halfheaven.plan.reel import Reel
from halfheaven.plan.overrides import apply_overrides
from halfheaven.analyze.framing import detect_letterbox
from halfheaven.analyze.grade import measure_color_stats
from halfheaven.render.lut import ColorStats, write_lut
from halfheaven.render.video import render
from halfheaven.schemas import Canvas, Look


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply one video's edit style to another.")
    parser.add_argument("--reference", required=True, help="an edited video to copy the style of")
    parser.add_argument("--target", required=True, nargs="+",
                        help="the footage to apply that style to; several takes are "
                             "treated as one, in the order given")
    parser.add_argument("--out", default="out.mp4")
    parser.add_argument("--work", default="work")
    parser.add_argument("--music", default="", help="a bed to mix under the speech")
    parser.add_argument("--overrides", default="",
                        help="JSON patch over the measured style profile")
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
        print(f"      type: body={profile.captions.font_category} "
              f"({profile.captions.size_pct:.3f}) "
              f"emphasis={profile.emphasis.font_category} "
              f"({profile.emphasis.size_pct:.3f})")
    if profile.framing.letterbox_top_pct or profile.framing.letterbox_bottom_pct:
        print(f"      letterbox {profile.framing.letterbox_top_pct:.3f} / "
              f"{profile.framing.letterbox_bottom_pct:.3f}")
    if profile.grade.measured:
        print(f"      grade LAB mean={tuple(round(v, 1) for v in profile.grade.lab_mean)} "
              f"std={tuple(round(v, 1) for v in profile.grade.lab_std)}")
    if args.overrides:
        # What the creator asked for, layered over what we measured.
        patch = json.loads(args.overrides)
        profile = apply_overrides(profile, patch)
        print(f"      adjusted: {', '.join(sorted(patch))}")
    (work / "style_profile.json").write_text(profile.model_dump_json(indent=2))

    takes = list(args.target)
    label = takes[0] if len(takes) == 1 else f"{len(takes)} takes"
    print(f"[2/5] transcribing {label}")

    infos = [probe(t) for t in takes]
    silent = [t for t, i in zip(takes, infos) if not i.has_audio]
    if silent:
        print(f"      no audio track in {', '.join(pathlib.Path(t).name for t in silent)} - "
              "the speech engine needs one", file=sys.stderr)
        return 2

    # Several takes are transcribed separately and their word times shifted onto
    # one clock, so everything downstream keeps working on a single timeline and
    # only the renderer needs to know which file a piece came from.
    words: list = []
    elapsed = 0.0
    for index, (take, info) in enumerate(zip(takes, infos)):
        part = client.transcribe(extract_audio(take, work / f"take_{index}.wav"))
        words += [
            dataclasses.replace(w, start=w.start + elapsed, end=w.end + elapsed)
            for w in part.words
        ]
        elapsed += info.duration
        if len(takes) > 1:
            print(f"      {pathlib.Path(take).name}: {len(part.words)} words, {info.duration:.1f}s")

    transcript = Transcript(words=words, duration=elapsed,
                            text=" ".join(w.text for w in words))
    target_info = infos[0]
    reel = Reel([(t, i.duration) for t, i in zip(takes, infos)]) if len(takes) > 1 else None
    print(f"      {len(transcript.words)} words over {transcript.duration:.1f}s")

    print("[3/5] editorial pass")
    decisions = decide(client, transcript, profile)
    if args.music:
        profile = profile.model_copy(update={
            "music": profile.music.model_copy(update={"present": True})})
    decisions = dataclasses.replace(
        decisions,
        music_src=args.music or None,
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
          f"{len(decisions.punch_word_indices)} punch-ins, "
          f"{len(decisions.emphasis_word_indices)} emphasised words")

    print("[4/5] building program")
    # The canvas follows the reference, not the upload: we are copying its
    # format as well as its look, and a wide upload should become vertical
    # rather than staying wide.
    reference_info = probe(args.reference)
    canvas = Canvas(width=reference_info.width, height=reference_info.height,
                    fps=target_info.fps)

    tracker = None
    if needs_reframe(target_info, canvas):
        # Centre-cropping a wide source discards most of the frame, so follow
        # the speaker rather than hoping they stand in the middle.
        print(f"      reframing {target_info.width}x{target_info.height} "
              f"-> {canvas.width}x{canvas.height}, following the subject")
        # Tracking reads one file, so it applies to a single take; several
        # takes fall back to the framing pattern.
        tracker = None if reel else (lambda spans: track_subject(takes[0], spans))

    program = build_program(
        source=str(takes[0]),
        canvas=canvas,
        transcript=transcript,
        profile=profile,
        decisions=decisions,
        tracker=tracker,
        reel=reel,
    )
    look = Look(
        letterbox_top_pct=profile.framing.letterbox_top_pct,
        letterbox_bottom_pct=profile.framing.letterbox_bottom_pct,
    )
    if profile.grade.measured:
        # Source stats are the target's own look; target stats are the
        # reference's. Strength is a dial because pushing bright footage all the
        # way to a dark reference turns it muddy.
        # Measured from the first take: several takes of the same setup share a
        # look, and sampling every one of them buys nothing.
        primary = takes[0]
        target_stats = measure_color_stats(primary, framing=detect_letterbox(primary))
        lut = write_lut(
            source=target_stats,
            target=ColorStats(mean=profile.grade.lab_mean, std=profile.grade.lab_std),
            out_path=work / "grade.cube",
            strength=profile.grade.strength,
        )
        look = look.model_copy(update={"lut": str(lut)})
        print(f"      grade: target LAB mean={tuple(round(v, 1) for v in target_stats.mean)} "
              f"-> reference, strength {profile.grade.strength}")
    program = program.model_copy(
        update={
            "styles": {"default": profile.captions, "emphasis": profile.emphasis},
            "look": look,
        }
    )
    (work / "edit_program.json").write_text(program.model_dump_json(indent=2))
    reveal = sum(1 for c in program.captions if c.reveals_word_by_word)
    stressed = sum(1 for c in program.captions for r in c.runs if r.style == "emphasis")
    print(f"      {len(program.video)} clips, {program.duration:.1f}s "
          f"(from {sum(i.duration for i in infos):.1f}s), {len(program.captions)} captions "
          f"({reveal} word-by-word, {stressed} stressed words)")

    print(f"[5/5] rendering -> {args.out}")
    render(program, args.out, work_dir=work)
    print(f"done: {args.out}  ({probe(args.out).duration:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
