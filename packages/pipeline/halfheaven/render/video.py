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
import json
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
# Mattes are resampled and composited, so they are kept close to lossless.
MASK_CRF = 10


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


def _geometry(clip: VideoClip, canvas: Canvas) -> list[str]:
    """The filters that frame a clip: cover, crop onto the subject, rate, punch-in.

    Computed from the footage's own size, so a matte of that footage - at any
    resolution, as long as the aspect matches - is scaled to the same cover and
    lands on the same pixels.
    """
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
    return filters


def build_segment_command(
    clip: VideoClip,
    canvas: Canvas,
    out_path: str | pathlib.Path,
    with_audio: bool,
) -> list[str]:
    """Render one clip. Exactly one input, so memory is bounded by one clip."""
    filters = _geometry(clip, canvas) + ["setsar=1", "format=yuv420p"]

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


def build_mask_segment_command(
    clip: VideoClip,
    mask_src: str | pathlib.Path,
    canvas: Canvas,
    out_path: str | pathlib.Path,
) -> list[str]:
    """Cut a take's matte exactly as `clip` cuts the take: same span, crop and zoom."""
    filters = _geometry(clip, canvas) + ["setsar=1", "format=gray"]
    return [
        ffmpeg(), "-v", "error", "-y",
        "-ss", f"{clip.start:.4f}", "-to", f"{clip.end:.4f}", "-i", str(mask_src),
        "-vf", ",".join(filters), "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(MASK_CRF), "-pix_fmt", "gray",
        "-fps_mode", "cfr", "-video_track_timescale", "90000",
        str(out_path),
    ]


def mask_track(program: EditProgram, kind: str, work_dir: str | pathlib.Path) -> pathlib.Path | None:
    """One of the takes' mattes ("subject" or "skin") cut into the program timeline.

    None unless every clip's take has that matte on disk: a matte missing for
    one clip would leave the effect on some shots and not others, which reads
    as a fault rather than a style. Reused when nothing it depends on changed,
    because the planner reads the subject track before the render does.
    """
    mattes = program.look.mattes
    sources: list[str] = []
    for clip in program.video:
        matte = mattes.get(clip.src)
        source = getattr(matte, kind, None) if matte else None
        if not source or not os.path.exists(source):
            return None
        sources.append(source)

    work_dir = pathlib.Path(work_dir).resolve()
    track = work_dir / f"{kind}_track.mp4"
    stamp = work_dir / f"{kind}_track.json"
    key = json.dumps({
        "canvas": program.canvas.model_dump(),
        "clips": [clip.model_dump() for clip in program.video],
        "sources": [(s, os.path.getmtime(s)) for s in sources],
    }, sort_keys=True)
    if track.exists() and stamp.exists() and stamp.read_text() == key:
        return track

    pieces_dir = work_dir / f"{kind}_segments"
    pieces_dir.mkdir(parents=True, exist_ok=True)
    pieces: list[pathlib.Path] = []
    for index, (clip, source) in enumerate(zip(program.video, sources)):
        piece = pieces_dir / f"seg_{index:04d}.mp4"
        _run(build_mask_segment_command(clip, source, program.canvas, piece), f"{kind} matte {index}")
        pieces.append(piece)
    listing = work_dir / f"{kind}_segments.txt"
    listing.write_text("\n".join(f"file '{p.resolve()}'" for p in pieces) + "\n")
    _run([ffmpeg(), "-v", "error", "-y", "-f", "concat", "-safe", "0",
          "-i", str(listing), "-c", "copy", str(track)], f"{kind} matte concat")
    stamp.write_text(key)
    return track


def build_finish_command(
    program: EditProgram,
    base_path: str | pathlib.Path,
    out_path: str | pathlib.Path,
    work_dir: str | pathlib.Path,
    has_speech: bool | None = None,
    subject_track: str | pathlib.Path | None = None,
    skin_track: str | pathlib.Path | None = None,
) -> list[str]:
    """Grade, letterbox and captions in one pass over the joined video.

    `subject_track` and `skin_track` are mattes already on the program
    timeline (see `mask_track`); `look.matte` stands in for a missing subject.
    """
    canvas = program.canvas
    width, height = canvas.width, canvas.height
    look = program.look

    top_px = int(round(look.letterbox_top_pct * height))
    bottom_px = int(round(look.letterbox_bottom_pct * height))
    content_h = max(2, height - top_px - bottom_px)
    letterbox = f"scale={width}:{content_h},pad={width}:{height}:0:{top_px}:black"

    inputs = ["-i", str(base_path)]
    # Counted explicitly: a concat input contributes four argv elements, not
    # two, so deriving indices from len(inputs) silently mislabels streams.
    input_count = 1
    steps: list[str] = []
    label = "[0:v]"

    def add_input(*args: str, kind: str = "v") -> str:
        nonlocal input_count
        inputs.extend(args)
        stream = f"[{input_count}:{kind}]"
        input_count += 1
        return stream

    if look.lut:
        # Grade before letterboxing so the bars stay pure black, and before the
        # captions so they keep the exact colour the profile asked for.
        lut = f"lut3d=file='{look.lut}':interp=tetrahedral"
        if skin_track and look.skin_protect > 0:
            # The graded picture is laid over the ungraded one with the skin
            # matte as its (inverted) alpha: everything takes the full grade,
            # skin takes `1 - skin_protect` of it.
            skin = add_input("-i", str(skin_track))
            steps.append(f"{label}split=2[ungraded][tograde]")
            steps.append(f"[tograde]{lut},format=yuva420p[graded]")
            steps.append(f"{skin}format=gray,lut=c0='255-val*{look.skin_protect:.3f}'[gradeweight]")
            steps.append("[graded][gradeweight]alphamerge[gradedskin]")
            steps.append("[ungraded][gradedskin]overlay=0:0[vg]")
        else:
            steps.append(f"{label}{lut}[vg]")
        label = "[vg]"
    subject = subject_track or look.matte
    behind = subject is not None and any(c.behind for c in program.captions)
    replace = subject is not None and look.background_hex is not None
    mattes: list[str] = []
    if behind or replace:
        # One read of the matte, split between the uses that need it.
        uses = int(behind) + int(replace)
        matte = add_input("-i", str(subject))
        if uses > 1:
            steps.append(f"{matte}split={uses}" + "".join(f"[matte{k}]" for k in range(uses)))
            mattes = [f"[matte{k}]" for k in range(uses)]
        else:
            mattes = [matte]

    if replace:
        # After the grade, so the plate is exactly the colour asked for; before
        # the letterbox, so the bars stay black.
        plate = look.background_hex.lstrip("#")
        steps.append(f"{label}split=2[plate][person]")
        steps.append(f"[plate]drawbox=c=0x{plate}@1:t=fill[platefill]")
        steps.append("[person]format=yuva420p[persona]")
        steps.append(f"[persona]{mattes.pop(0)}alphamerge[cutout]")
        steps.append("[platefill][cutout]overlay=0:0:eof_action=pass[vr]")
        label = "[vr]"

    if look.is_letterboxed:
        steps.append(f"{label}{letterbox}[vp]")
        label = "[vp]"

    if behind:
        # Three layers: captions marked behind, the subject cut out of the
        # picture and laid back on top of them, then every other caption.
        behind_stream = add_input("-f", "concat", "-safe", "0", "-i",
                                  str(build_caption_track(program, work_dir, layer="behind")))
        front_stream = None
        if any(not c.behind for c in program.captions):
            front_stream = add_input("-f", "concat", "-safe", "0", "-i",
                                     str(build_caption_track(program, work_dir, layer="front")))
        matte = mattes.pop(0)
        if look.is_letterboxed:
            # the matte follows the picture into the letterbox
            steps.append(f"{matte}{letterbox}[matteboxed]")
            matte = "[matteboxed]"
        steps.append(f"{label}split=2[bg][fg]")
        steps.append(f"[bg]{behind_stream}overlay=0:0:eof_action=pass[withcap]")
        steps.append("[fg]format=yuva420p[fga]")
        steps.append(f"[fga]{matte}alphamerge[subject]")
        steps.append("[withcap][subject]overlay=0:0:eof_action=pass[vs]")
        label = "[vs]"
        if front_stream:
            steps.append(f"{label}{front_stream}overlay=0:0:eof_action=pass[vc]")
            label = "[vc]"
    elif program.captions:
        # One caption track, one overlay: constant cost in the caption count.
        caption_stream = add_input("-f", "concat", "-safe", "0", "-i",
                                   str(build_caption_track(program, work_dir)))
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
        bed = add_input("-stream_loop", "-1", "-i", str(music.src), kind="a")
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

    look = program.look
    needs_subject = look.background_hex is not None or any(c.behind for c in program.captions)
    subject = mask_track(program, "subject", work_dir) if needs_subject else None
    skin = mask_track(program, "skin", work_dir) if look.lut and look.skin_protect > 0 else None
    _run(build_finish_command(program, base, out_path, work_dir, with_audio,
                              subject_track=subject, skin_track=skin), "finish")
    return out_path
