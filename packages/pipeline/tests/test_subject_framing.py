"""A framing is only right if the rendered frame is right.

Every earlier test of framing read `program.video` - the numbers the planner
wrote - and every one of them passed while the renderer threw those numbers
away. `crop_x` moved nothing, and the punch-ins zoomed toward the top-left
corner. So these tests render a real segment and look at where the subject
ends up in the picture.

The subject is a white square on grey, placed exactly, because a known position
is the only way to say where it should land.
"""
from __future__ import annotations

import pathlib
import subprocess

import cv2
import numpy as np
import pytest

from halfheaven.analyze.subject import (
    HEADROOM,
    Face,
    find_subject_prompt,
    locate_subject,
    track_subject,
)
from halfheaven.media.ffmpeg_bin import ffmpeg
from halfheaven.media.probe import probe
from halfheaven.render.video import build_segment_command
from halfheaven.schemas import Canvas, VideoClip

CANVAS = Canvas(width=360, height=640, fps=30)
WIDE_FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "wide_subject_moves.mp4"


def _subject_clip(tmp_path, name: str, size: tuple[int, int],
                  at: tuple[float, float], side: int = 36, duration: float = 1.0) -> pathlib.Path:
    width, height = size
    x, y = int(at[0] * width - side / 2), int(at[1] * height - side / 2)
    out = tmp_path / f"{name}.mp4"
    subprocess.run(
        [ffmpeg(), "-v", "error", "-y", "-f", "lavfi",
         "-i", f"color=c=0x404040:s={width}x{height}:d={duration}:r=30",
         "-vf", f"drawbox=x={x}:y={y}:w={side}:h={side}:color=white:t=fill",
         "-pix_fmt", "yuv420p", str(out)],
        check=True, capture_output=True,
    )
    return out


def _render(tmp_path, source: pathlib.Path, tag: str, **framing) -> pathlib.Path:
    out = tmp_path / f"seg_{tag}.mp4"
    clip = VideoClip(src=str(source), start=0.0, end=1.0, **framing)
    subprocess.run(build_segment_command(clip, CANVAS, out, with_audio=False),
                   check=True, capture_output=True)
    return out


def _settled_frame(video: pathlib.Path) -> np.ndarray:
    capture = cv2.VideoCapture(str(video))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, count - 2))
    ok, frame = capture.read()
    capture.release()
    assert ok, f"could not read {video}"
    return frame


def _square_at(video: pathlib.Path) -> tuple[float, float] | None:
    """Where the white square sits once the punch has settled, or None."""
    gray = cv2.cvtColor(_settled_frame(video), cv2.COLOR_BGR2GRAY)
    ys, xs = np.nonzero(gray > 200)
    if xs.size < 20:
        return None
    return float(xs.mean() / gray.shape[1]), float(ys.mean() / gray.shape[0])


# --------------------------------------------------------------------------
# the renderer honours the subject point
# --------------------------------------------------------------------------


def test_a_punch_zooms_into_the_subject(tmp_path):
    source = _subject_clip(tmp_path, "tall", (360, 640), (0.35, 0.40))
    where = _square_at(_render(tmp_path, source, "on", scale_to=2.0, crop_x=0.35, crop_y=0.40))
    assert where is not None, "the subject left the frame"
    assert where == pytest.approx((0.5, 0.5), abs=0.06)


def test_without_a_subject_point_a_punch_holds_the_centre(tmp_path):
    """The bug this replaces anchored every zoom on the top-left corner, which
    slid anything in the middle down and to the right as the punch grew."""
    source = _subject_clip(tmp_path, "mid", (360, 640), (0.5, 0.5))
    where = _square_at(_render(tmp_path, source, "centre", scale_to=1.5))
    assert where == pytest.approx((0.5, 0.5), abs=0.04)


def test_the_subject_point_moves_the_picture(tmp_path):
    source = _subject_clip(tmp_path, "off", (360, 640), (0.35, 0.40))
    followed = _square_at(_render(tmp_path, source, "follow", scale_to=2.0, crop_x=0.35, crop_y=0.40))
    ignored = _square_at(_render(tmp_path, source, "ignore", scale_to=2.0))
    assert followed and ignored
    assert followed[0] - ignored[0] > 0.2, "the crop did not move toward the subject"


def test_a_wide_source_reframes_onto_the_subject_without_a_punch(tmp_path):
    source = _subject_clip(tmp_path, "wide", (640, 360), (0.8, 0.5), side=30)
    followed = _square_at(_render(tmp_path, source, "wide_on", crop_x=0.8))
    centred = _square_at(_render(tmp_path, source, "wide_off"))
    assert followed is not None and followed[0] == pytest.approx(0.5, abs=0.08)
    # a centre crop of a wide frame cuts a subject at 0.8 out entirely
    assert centred is None


def test_a_punch_keeps_one_output_frame_per_input_frame(tmp_path):
    """zoompan was once dropped for emitting hundreds of frames per input."""
    source = _subject_clip(tmp_path, "count", (360, 640), (0.5, 0.5))
    capture = cv2.VideoCapture(str(_render(tmp_path, source, "count", scale_to=1.3)))
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    assert 28 <= frames <= 31


# --------------------------------------------------------------------------
# finding the subject: a face first, motion when there is none
# --------------------------------------------------------------------------


class _Faces:
    """Stands in for YuNet, so the policy is testable without a model."""

    def __init__(self, face: Face | None) -> None:
        self._face = face

    def faces(self, frame):
        return [self._face] if self._face else []


def test_a_face_wins_over_motion():
    face = Face(x=0.72, y=0.40, height=0.2, score=0.9)
    x, y = locate_subject(WIDE_FIXTURE, [(0.2, 1.2)], detector=_Faces(face))[0]
    assert x == pytest.approx(0.72, abs=0.01)
    assert y == pytest.approx(0.40 + HEADROOM, abs=0.01)


def test_without_a_face_it_falls_back_to_motion():
    blind = _Faces(None)
    spans = [(0.2, 1.2), (3.2, 4.2)]
    located = locate_subject(WIDE_FIXTURE, spans, detector=blind)
    assert [x for x, _ in located] == track_subject(WIDE_FIXTURE, spans, detector=blind)
    assert located[0][0] < 0.45 < 0.55 < located[1][0], "motion no longer follows the subject"
    assert all(y == 0.5 for _, y in located)


def test_the_segmenter_is_prompted_on_the_face(tmp_path):
    source = _subject_clip(tmp_path, "prompt", (360, 640), (0.5, 0.5))
    face = Face(x=0.30, y=0.35, height=0.15, score=0.9)
    prompt = find_subject_prompt(source, detector=_Faces(face))
    assert all(abs(x - 0.30 * 360) < 3 for x, _ in prompt.points)
    face_y, chest_y = (y for _, y in prompt.points)
    assert face_y == pytest.approx(0.35 * 640, abs=3)
    assert chest_y > face_y, "the second point should sit below the face"


# --------------------------------------------------------------------------
# phone footage arrives turned
# --------------------------------------------------------------------------


def test_a_rotated_phone_clip_is_measured_and_framed_upright(tmp_path):
    """Phones store portrait video as landscape pixels plus an instruction to
    turn them. ffmpeg and OpenCV obey it, so every frame read is portrait - but
    the stream's width and height describe the stored pixels. Sized from those,
    the renderer stretched the picture about three times sideways."""
    stored = tmp_path / "stored.mp4"
    subprocess.run(
        [ffmpeg(), "-v", "error", "-y", "-f", "lavfi",
         "-i", "color=c=0x404040:s=640x360:d=1:r=30,"
               "drawbox=x=40:y=40:w=80:h=40:color=white:t=fill",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(stored)],
        check=True, capture_output=True,
    )
    turned = tmp_path / "turned.mp4"
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-display_rotation", "90",
                    "-i", str(stored), "-c", "copy", str(turned)],
                   check=True, capture_output=True)

    info = probe(turned)
    assert (info.width, info.height) == (360, 640), "probe reported the stored size"

    gray = cv2.cvtColor(_settled_frame(_render(tmp_path, turned, "turned")), cv2.COLOR_BGR2GRAY)
    ys, xs = np.nonzero(gray > 200)
    width, height = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    # an 80x40 box turned a quarter reads 40x80; squashed it reads about 126x80
    assert height / width == pytest.approx(2.0, abs=0.25), "the picture was squashed"
