"""EditProgram -> MP4.

A pure function of the program. The renderer never sees a StyleProfile, a
transcript, or a model response - if the output is wrong, the program that
produced it can be read, diffed and replayed.

Captions are composited as Pillow-rendered RGBA overlays rather than drawn with
drawtext, which does not exist in every ffmpeg build and cannot do per-word
highlighting.
"""
from __future__ import annotations

import pathlib
import subprocess

from halfheaven.media.ffmpeg_bin import ffmpeg
from halfheaven.media.probe import probe
from halfheaven.render.captions import render_caption
from halfheaven.schemas import CaptionProfile, EditProgram


def extract_frame(video: str | pathlib.Path, at: float, out_path: str | pathlib.Path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    subprocess.run(
        [ffmpeg(), "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(video),
         "-frames:v", "1", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def render(
    program: EditProgram,
    out_path: str | pathlib.Path,
    work_dir: str | pathlib.Path,
) -> pathlib.Path:
    out_path, work_dir = pathlib.Path(out_path), pathlib.Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    canvas = program.canvas
    width, height, fps = canvas.width, canvas.height, canvas.fps
    duration = program.duration

    sources = list(dict.fromkeys(clip.src for clip in program.video))
    source_index = {src: i for i, src in enumerate(sources)}
    # Audio only survives if every source has some; otherwise concat would be
    # asked to join streams that do not exist.
    with_audio = all(probe(src).has_audio for src in sources)

    inputs: list[str] = []
    for src in sources:
        inputs += ["-i", str(src)]

    steps: list[str] = []
    concat_labels: list[str] = []
    for i, clip in enumerate(program.video):
        stream = source_index[clip.src]
        zoom = clip.scale_to or 1.0
        steps.append(
            f"[{stream}:v]trim=start={clip.start:.4f}:end={clip.end:.4f},"
            f"setpts=PTS-STARTPTS,"
            f"scale={int(width * zoom)}:{int(height * zoom)}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={fps},setsar=1[v{i}]"
        )
        concat_labels.append(f"[v{i}]")
        if with_audio:
            steps.append(
                f"[{stream}:a]atrim=start={clip.start:.4f}:end={clip.end:.4f},"
                f"asetpts=PTS-STARTPTS,"
                f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a{i}]"
            )
            concat_labels.append(f"[a{i}]")

    n = len(program.video)
    if with_audio:
        steps.append("".join(concat_labels) + f"concat=n={n}:v=1:a=1[vcat][acat]")
    else:
        steps.append("".join(concat_labels) + f"concat=n={n}:v=1:a=0[vcat]")

    # Caption cards: one still image input each, bounded to the program length
    # so the graph terminates.
    video_label = "[vcat]"
    next_input = len(sources)
    for i, caption in enumerate(program.captions):
        style = program.styles.get(caption.style) or CaptionProfile(present=True)
        card = render_caption(caption.text, canvas, style, work_dir / f"caption_{i:04d}.png")
        inputs += ["-loop", "1", "-t", f"{duration:.4f}", "-i", str(card)]
        end = caption.t + caption.duration
        steps.append(
            f"{video_label}[{next_input}:v]"
            f"overlay=0:0:enable='between(t,{caption.t:.4f},{end:.4f})'[vo{i}]"
        )
        video_label = f"[vo{i}]"
        next_input += 1

    command = [ffmpeg(), "-v", "error", "-y", *inputs,
               "-filter_complex", ";".join(steps),
               "-map", video_label]
    if with_audio:
        command += ["-map", "[acat]", "-c:a", "aac", "-b:a", "160k"]
    command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", str(out_path)]

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg render failed:\n{result.stderr[-2000:]}")
    return out_path
