"""EditProgram -> MP4.

A pure function of the program: the renderer never sees a StyleProfile, a
transcript, or a model response.

Rendered as one small ffmpeg process per clip, joined with the concat DEMUXER,
then a single finishing pass for grade, letterbox and captions.

That structure is not incidental. Expressing the whole edit as one filtergraph
with `concat=n=16` across sixteen `-i` inputs was killed three times at
3.5-4.8GB: the concat filter consumes segments in order, but ffmpeg opens every
input at once, so the fifteen not-yet-consumed decoders ran ahead buffering
720x1280 frames they could not deliver. Removing audio changed nothing and
removing captions changed nothing, which is what identified the concat filter
rather than either of them. The concat demuxer opens files one at a time, so
peak memory is bounded by a single clip no matter how long the edit is.
"""
from __future__ import annotations

import pathlib
import subprocess

from halfheaven.media.ffmpeg_bin import ffmpeg
from halfheaven.media.probe import probe
from halfheaven.render.captions import build_caption_track
from halfheaven.schemas import Canvas, EditProgram, VideoClip

# A punch-in that snaps is invisible; one that eases over half a second reads as
# deliberate camera emphasis.
PUNCH_SECONDS = 0.5
# Intermediates are re-encoded once more in the finish pass, so keep them clean.
SEGMENT_CRF = 16
OUTPUT_CRF = 20


def _zoom_expression(scale_to: float) -> str:
    """Ease-out-cubic from 1.0 to `scale_to` over PUNCH_SECONDS, driven by `t`.

    Evaluated by `scale` with eval=frame. zoompan was the obvious filter for
    this and is the wrong one: its d=1 did not take effect and it emitted ~512
    output frames per input frame, turning an 11.3s clip into 5792s. `crop`
    cannot do it either - crop evaluates width and height once at configuration
    time, where `t` does not exist. `scale` with eval=frame re-evaluates every
    frame and preserves the frame count.
    """
    amount = scale_to - 1.0
    progress = f"min(1,t/{PUNCH_SECONDS})"
    return f"(1+{amount:.4f}*(1-pow(1-{progress},3)))"


def build_segment_command(
    clip: VideoClip,
    canvas: Canvas,
    out_path: str | pathlib.Path,
    with_audio: bool,
) -> list[str]:
    """Render one clip. Exactly one input, so memory is bounded by one clip."""
    width, height, fps = canvas.width, canvas.height, canvas.fps

    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
    ]
    if clip.scale_to and clip.scale_to > 1.0:
        zoom = _zoom_expression(clip.scale_to)
        # Dimensions rounded to even numbers; yuv420p cannot encode odd ones.
        filters.append(
            f"scale=w='trunc(iw*{zoom}/2)*2':h='trunc(ih*{zoom}/2)*2':eval=frame"
        )
        filters.append(f"crop={width}:{height}")
    filters += [f"fps={fps}", "setsar=1", "format=yuv420p"]

    command = [
        ffmpeg(), "-v", "error", "-y",
        "-ss", f"{clip.start:.4f}", "-to", f"{clip.end:.4f}", "-i", str(clip.src),
        "-vf", ",".join(filters),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(SEGMENT_CRF),
        "-fps_mode", "cfr", "-video_track_timescale", "90000",
    ]
    # Every segment must share codec parameters or the concat demuxer cannot
    # stream-copy them together.
    if with_audio:
        command += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    else:
        command += ["-an"]
    command.append(str(out_path))
    return command


def build_finish_command(
    program: EditProgram,
    base_path: str | pathlib.Path,
    out_path: str | pathlib.Path,
    work_dir: str | pathlib.Path,
) -> list[str]:
    """Grade, letterbox and captions in one pass over the joined video."""
    canvas = program.canvas
    width, height = canvas.width, canvas.height
    look = program.look

    top_px = int(round(look.letterbox_top_pct * height))
    bottom_px = int(round(look.letterbox_bottom_pct * height))
    content_h = max(2, height - top_px - bottom_px)

    inputs = ["-i", str(base_path)]
    # Counted explicitly: a concat input contributes four argv elements, not
    # two, so deriving indices from len(inputs) silently mislabels streams.
    input_count = 1
    steps: list[str] = []
    label = "[0:v]"

    if look.lut:
        # Grade before letterboxing so the bars stay pure black, and before the
        # captions so they keep the exact colour the profile asked for.
        steps.append(f"{label}lut3d=file='{look.lut}':interp=tetrahedral[vg]")
        label = "[vg]"
    if look.is_letterboxed:
        steps.append(
            f"{label}scale={width}:{content_h},pad={width}:{height}:0:{top_px}:black[vp]"
        )
        label = "[vp]"
    caption_stream: str | None = None
    if program.captions:
        # One caption track, one overlay: constant cost in the caption count.
        listing = build_caption_track(program, work_dir)
        inputs += ["-f", "concat", "-safe", "0", "-i", str(listing)]
        caption_stream = f"[{input_count}:v]"
        input_count += 1

    if look.matte:
        # Split the picture: one copy takes the caption, the other becomes the
        # cut-out subject that is laid back on top. That ordering is the effect.
        inputs += ["-i", str(look.matte)]
        matte_stream = f"[{input_count}:v]"
        input_count += 1
        steps.append(f"{label}split=2[bg][fg]")
        if caption_stream:
            steps.append(f"[bg]{caption_stream}overlay=0:0:eof_action=pass[withcap]")
            under = "[withcap]"
        else:
            under = "[bg]"
        steps.append(f"[fg]format=yuva420p[fga]")
        steps.append(f"[fga]{matte_stream}alphamerge[subject]")
        steps.append(f"{under}[subject]overlay=0:0:eof_action=pass[vc]")
        label = "[vc]"
    elif caption_stream:
        steps.append(f"{label}{caption_stream}overlay=0:0:eof_action=pass[vc]")
        label = "[vc]"

    command = [ffmpeg(), "-v", "error", "-y", *inputs]
    if steps:
        command += ["-filter_complex", ";".join(steps), "-map", label]
    else:
        command += ["-map", "0:v"]
    command += ["-map", "0:a?", "-c:a", "copy",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", str(OUTPUT_CRF),
                "-pix_fmt", "yuv420p", str(out_path)]
    return command


def extract_frame(video: str | pathlib.Path, at: float, out_path: str | pathlib.Path) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    subprocess.run(
        [ffmpeg(), "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(video),
         "-frames:v", "1", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def _run(command: list[str], what: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg {what} failed (exit {result.returncode})\n"
            f"stderr:\n{result.stderr[-1500:] or '(empty)'}\n"
            f"command:\n  {' '.join(command)}"
        )


def render(
    program: EditProgram,
    out_path: str | pathlib.Path,
    work_dir: str | pathlib.Path,
) -> pathlib.Path:
    out_path = pathlib.Path(out_path)
    work_dir = pathlib.Path(work_dir).resolve()
    segments_dir = work_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    with_audio = all(probe(clip.src).has_audio for clip in program.video)

    segments: list[pathlib.Path] = []
    for index, clip in enumerate(program.video):
        segment = segments_dir / f"seg_{index:04d}.mp4"
        _run(build_segment_command(clip, program.canvas, segment, with_audio), f"segment {index}")
        segments.append(segment)

    listing = work_dir / "segments.txt"
    listing.write_text("\n".join(f"file '{p.resolve()}'" for p in segments) + "\n")
    base = work_dir / "base.mp4"
    _run(
        [ffmpeg(), "-v", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(base)],
        "concat",
    )

    _run(build_finish_command(program, base, out_path, work_dir), "finish")
    return out_path
