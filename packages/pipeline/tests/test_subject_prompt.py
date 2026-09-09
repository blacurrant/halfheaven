"""Finding the subject to prompt a segmenter with.

SAM2 tracks whatever it is pointed at, so something has to point. OpenCV's
headless build ships no Haar cascades, and a face detector would be the wrong
tool anyway: what we want is "the thing that moves", which for a locked-off
talking head is exactly the speaker. Temporal variance finds it with no model
and no extra dependency.
"""
import pathlib
import subprocess

import numpy as np
import pytest
from PIL import Image, ImageDraw

from halfheaven.analyze.subject import find_subject_prompt
from halfheaven.media.ffmpeg_bin import ffmpeg

W, H, FRAMES = 320, 568, 40


def _make_video(path, blob_centre_x, moving=True):
    """A still room with one blob that may or may not move."""
    frames_dir = path.parent / f"frames_{path.stem}"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i in range(FRAMES):
        image = Image.new("RGB", (W, H), (30, 30, 40))
        draw = ImageDraw.Draw(image)
        for k in range(5):  # static background structure
            draw.rectangle([k * 64, 60, k * 64 + 40, 140], fill=(70, 70, 90))
        wobble = int(14 * np.sin(i / 3.0)) if moving else 0
        x = blob_centre_x + wobble
        draw.ellipse([x - 45, 200 + wobble, x + 45, 380 + wobble], fill=(210, 180, 160))
        image.save(frames_dir / f"{i:04d}.png")
    subprocess.run(
        [ffmpeg(), "-v", "error", "-y", "-framerate", "30", "-i", f"{frames_dir}/%04d.png",
         "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True,
    )
    return path


@pytest.fixture(scope="module")
def moving_left(tmp_path_factory):
    return _make_video(tmp_path_factory.mktemp("v") / "left.mp4", blob_centre_x=80)


@pytest.fixture(scope="module")
def moving_right(tmp_path_factory):
    return _make_video(tmp_path_factory.mktemp("v") / "right.mp4", blob_centre_x=240)


@pytest.fixture(scope="module")
def static_scene(tmp_path_factory):
    return _make_video(tmp_path_factory.mktemp("v") / "still.mp4", blob_centre_x=160, moving=False)


def test_a_prompt_has_at_least_one_point(moving_left):
    assert len(find_subject_prompt(moving_left).points) >= 1


def test_every_point_is_marked_foreground(moving_left):
    prompt = find_subject_prompt(moving_left)
    assert set(prompt.labels) == {1}
    assert len(prompt.labels) == len(prompt.points)


def test_every_point_lies_inside_the_frame(moving_left):
    for x, y in find_subject_prompt(moving_left).points:
        assert 0 <= x < W and 0 <= y < H


def test_it_finds_a_subject_on_the_left(moving_left):
    xs = [x for x, _ in find_subject_prompt(moving_left).points]
    assert np.mean(xs) < W * 0.45


def test_it_finds_a_subject_on_the_right(moving_right):
    xs = [x for x, _ in find_subject_prompt(moving_right).points]
    assert np.mean(xs) > W * 0.55


def test_a_static_scene_falls_back_to_the_centre(static_scene):
    xs = [x for x, _ in find_subject_prompt(static_scene).points]
    assert np.mean(xs) == pytest.approx(W / 2, abs=W * 0.12)


def test_points_span_the_body_not_just_one_spot(moving_left):
    ys = sorted(y for _, y in find_subject_prompt(moving_left).points)
    assert ys[-1] - ys[0] > H * 0.1, "a single point risks latching onto only the face"


# --- background motion --------------------------------------------------------
# Measured on real footage: in noedit.mp4 the motion centroid landed at x=0.80,
# on the plant and shelving behind the speaker, who is centred. Background
# movement, camera noise and compression all register as motion, so motion may
# nudge the prompt but must never drag it off the subject.


@pytest.fixture(scope="module")
def busy_background(tmp_path_factory):
    """A centred, still speaker in front of a strongly moving background."""
    path = tmp_path_factory.mktemp("v") / "busy.mp4"
    frames_dir = path.parent / "frames_busy"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i in range(FRAMES):
        image = Image.new("RGB", (W, H), (30, 30, 40))
        draw = ImageDraw.Draw(image)
        # a lot of movement down the right-hand edge
        for k in range(6):
            offset = int(30 * np.sin(i / 2.0 + k))
            draw.rectangle([250, 40 + k * 80 + offset, 318, 100 + k * 80 + offset],
                           fill=(200, 120, 90))
        draw.ellipse([115, 200, 205, 380], fill=(210, 180, 160))  # still, centred
        image.save(frames_dir / f"{i:04d}.png")
    subprocess.run(
        [ffmpeg(), "-v", "error", "-y", "-framerate", "30", "-i", f"{frames_dir}/%04d.png",
         "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True,
    )
    return path


def test_background_motion_does_not_drag_the_prompt_off_the_subject(busy_background):
    xs = [x for x, _ in find_subject_prompt(busy_background).points]
    assert np.mean(xs) == pytest.approx(W / 2, abs=W * 0.15)


def test_the_prompt_never_leaves_the_central_region(moving_left, moving_right, busy_background):
    # composition puts a short-form subject near the centre; motion may nudge
    # the prompt but not relocate it
    for video in (moving_left, moving_right, busy_background):
        xs = [x for x, _ in find_subject_prompt(video).points]
        assert abs(np.mean(xs) - W / 2) <= W * 0.16
