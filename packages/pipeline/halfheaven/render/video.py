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

import os
import math
import functools
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


# zoompan places its window on whole input pixels, so a slow push visibly steps.
# Working at twice the canvas size halves that: measured on a still frame, the
# wobble at the zoom's fixed point fell from 0.93 px RMS to 0.51.
PUNCH_UPSCALE = 2


@functools.lru_cache(maxsize=64)
def _source_size(src: str) -> tuple[int, int] | None:
    """Source dimensions, or None when they cannot be read.

    A command builder should not crash on an unreadable path - ffmpeg will say
    so when it runs - so an unknown size simply means "no slack to move in".
    """
    try:
        info = probe(src)
    except Exception:
        return None
    return (info.width, info.height) if info.width and info.height else None


def _placement(source: int, window: int, centre: float) -> tuple[int, float]:
    """Where a `window`-long crop starts inside `source`, and where `centre` lands in it.

    The window is centred on the subject and then pushed back inside the
    picture, so near an edge the subject ends up off-centre rather than the crop
    running into black. Returns the offset in pixels and the subject's position
    inside the window as a fraction - which is what a punch-in must centre on.
    """
    slack = max(0, source - window)
    start = int(round(min(max(centre * source - window / 2, 0.0), slack)))
    inside = (centre * source - start) / window if window else 0.5
    return start, float(min(max(inside, 0.0), 1.0))


def _zoompan(scale_to: float, centre: tuple[float, float], canvas: Canvas) -> str:
    """A punch-in that grows toward the subject rather than toward a corner.

    Two earlier approaches were wrong in ways no test caught, because every test
    read the program instead of looking at a frame. `scale` with eval=frame grows
    the picture correctly, but `crop` fixes its input size when the graph is
    configured - at zoom 1.0, with no slack - so every offset after it clamps to
    zero. Its default centring is computed the same way, which anchored every
    punch-in on the top-left corner and slid the speaker down and right as it
    grew. zoompan evaluates its window per frame against a size it actually
    knows. It was once dropped for emitting hundreds of frames per input; with
    d=1 it emits one (measured on ffmpeg 9.0.1), and a test holds it there.

    The ease runs on `it`, the input timestamp in seconds, so it takes
    PUNCH_SECONDS whatever the source frame rate.
    """
    x, y = centre
    zoom = f"1+{scale_to - 1.0:.4f}*(1-pow(1-min(1\\,it/{PUNCH_SECONDS})\\,3))"
    left = f"max(0\\,min(iw*{x:.4f}-iw/zoom/2\\,iw-iw/zoom))"
    top = f"max(0\\,min(ih*{y:.4f}-ih/zoom/2\\,ih-ih/zoom))"
    return (f"zoompan=z='{zoom}':x='{left}':y='{top}':d=1"
            f":s={canvas.width}x{canvas.height}:fps={canvas.fps}")


def build_segment_command(
    clip: VideoClip,
    canvas: Canvas,
    out_path: str | pathlib.Path,
    with_audio: bool,
) -> list[str]:
    """Render one clip. Exactly one input, so memory is bounded by one clip."""
    width, height, fps = canvas.width, canvas.height, canvas.fps

    # Cover the canvas, then take a canvas-sized window centred on the subject.
    # Both sizes are fixed before the graph starts, which is the only moment
    # `crop` reads them - so this offset, unlike one placed after a zoom, is
    # actually honoured. Even dimensions: yuv420p cannot encode odd ones.
    size = _source_size(str(clip.src))
    if size:
        cover = max(width / size[0], height / size[1])
        cover_w = max(width, 2 * math.ceil(size[0] * cover / 2))
        cover_h = max(height, 2 * math.ceil(size[1] * cover / 2))
    else:
        cover_w, cover_h = width, height
    left, inside_x = _placement(cover_w, width, clip.crop_x)
    top, inside_y = _placement(cover_h, height, clip.crop_y)

    filters = [
        f"scale={cover_w}:{cover_h}",
        f"crop={width}:{height}:{left}:{top}",
        f"fps={fps}",
    ]
    if clip.scale_to and clip.scale_to > 1.0:
        if PUNCH_UPSCALE > 1:
            filters.append(f"scale={width * PUNCH_UPSCALE}:{height * PUNCH_UPSCALE}")
        filters.append(_zoompan(clip.scale_to, (inside_x, inside_y), canvas))
    filters += ["setsar=1", "format=yuv420p"]

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
    has_speech: bool | None = None,
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

    # A music bed is compressed against the speech itself, so it drops when
    # someone talks and returns in the gaps. That is what makes a bed sound
    # deliberate rather than merely loud.
    audio_map = ["-map", "0:a?", "-c:a", "copy"]
    music = program.music
    if has_speech is None:
        # Probe when we can; assume there is speech when the base has not been
        # rendered yet, which is the case when only the command is being built.
        has_speech = probe(base_path).has_audio if os.path.exists(base_path) else True

    if music and os.path.exists(music.src):
        inputs += ["-stream_loop", "-1", "-i", str(music.src)]
        bed = f"[{input_count}:a]"
        input_count += 1
        steps.append(
            f"{bed}volume={music.gain_db:.1f}dB,"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[bed]"
        )
        if has_speech:
            steps.append("[0:a]aformat=sample_fmts=fltp:sample_rates=48000:"
                         "channel_layouts=stereo,asplit=2[sp][key]")
            steps.append(
                f"[bed][key]sidechaincompress=threshold=0.02:ratio=8:"
                f"attack={max(1, int(music.duck_attack * 1000))}:"
                f"release={max(1, int(music.duck_release * 1000))}[ducked]"
            )
            # normalize=0 matters: amix divides by the number of inputs by
            # default, so adding a bed would quietly halve the speech and make
            # every video with music sound flatter than one without.
            steps.append("[sp][ducked]amix=inputs=2:duration=first:"
                         "dropout_transition=0:normalize=0,alimiter=limit=0.97[aout]")
        else:
            # Nothing to duck against, so the bed is simply the soundtrack.
            steps.append("[bed]alimiter=limit=0.97[aout]")
        audio_map = ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-shortest"]

    command = [ffmpeg(), "-v", "error", "-y", *inputs]
    if steps:
        # "[0:v]" is a stream specifier, not a filter label. Once a filtergraph
        # exists, mapping it in brackets is read as a label that was never
        # produced - which happens whenever music adds filters and the video
        # has none of its own.
        command += ["-filter_complex", ";".join(steps),
                    "-map", "0:v" if label == "[0:v]" else label]
    else:
        command += ["-map", "0:v"]
    command += [*audio_map,
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

    _run(build_finish_command(program, base, out_path, work_dir, with_audio), "finish")
    return out_path
