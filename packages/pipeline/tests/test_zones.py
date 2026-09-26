"""Reading a picture as zones: the subject, the room behind them, and skin."""
import subprocess

import numpy as np
import pytest

from halfheaven.analyze.segment import write_matte_video
from halfheaven.analyze.zones import read_zone_look, reference_zone_look, summarise, take_zone_look
from halfheaven.media.ffmpeg_bin import ffmpeg
from halfheaven.schemas import TakeMatte
from tests.zone_fakes import WIDE, Bright, ellipse_parts, tiny_parts

TIMES = [0.1 + 0.3 * i for i in range(14)]      # inside the 4.4s fixture


def split_frame(subject_lab=(60.0, 12.0, 14.0), background_lab=(18.0, 6.0, 1.0)):
    """100x100 LAB: left half subject, right half background, top-left quarter skin."""
    lab = np.zeros((100, 100, 3), np.float32)
    lab[:, :50] = subject_lab
    lab[:, 50:] = background_lab
    subject = np.zeros((100, 100), bool)
    subject[:, :50] = True
    skin = np.zeros((100, 100), bool)
    skin[:50, :50] = True
    return lab, subject, ~subject, skin


def test_each_zone_is_read_on_its_own():
    look = read_zone_look([split_frame()])
    assert look.subject.mean_l == pytest.approx(60.0)
    assert look.background.l_quantiles[50] == pytest.approx(18.0)
    assert look.skin.ab == pytest.approx((12.0, 14.0))


def test_the_split_tone_is_read_from_near_neutral_pixels():
    look = read_zone_look([split_frame()])
    assert look.background.tints[1] == pytest.approx((6.0, 1.0))    # the 12-25 band holds L 18
    assert look.background.shadow_tint_a == pytest.approx(6.0)
    # the subject's chroma is 18.4, not near-neutral, so it carries no tint
    assert look.subject.tints[3] == pytest.approx((0.0, 0.0))


def test_the_summary_is_what_the_scorecard_compares():
    summary = summarise(read_zone_look([split_frame()]))
    assert summary["face_above_background"] == pytest.approx(42.0)
    assert summary["background_l"] == pytest.approx(18.0)
    assert summary["skin_chroma"] == pytest.approx(18.44, abs=0.01)
    assert summary["skin_hue"] == pytest.approx(49.4, abs=0.1)
    assert summary["shadow_tint"] == pytest.approx(6.0)


def test_too_little_subject_reads_nothing():
    lab, subject, background, skin = split_frame()
    subject[:] = False
    subject[:10, :10] = True
    assert read_zone_look([(lab, subject, background, skin)]) is None


def test_without_skin_the_zones_are_still_read():
    lab, subject, background, skin = split_frame()
    look = read_zone_look([(lab, subject, background, np.zeros_like(skin))])
    assert look.skin is None
    summary = summarise(look)
    assert summary["skin_hue"] is None and summary["background_l"] == pytest.approx(18.0)


def test_a_take_is_read_through_its_own_mattes(tmp_path):
    matte = write_matte_video(WIDE, Bright(), tmp_path / "m.mp4", feather=0)
    look = take_zone_look([str(WIDE)], {str(WIDE): TakeMatte(subject=str(matte), skin=str(matte))})
    assert look.subject.mean_l > 70 and look.background.mean_l < 25
    assert look.skin is not None


def test_a_matte_smaller_than_its_take_is_scaled_to_it(tmp_path):
    full = write_matte_video(WIDE, Bright(), tmp_path / "m.mp4", feather=0)
    small = tmp_path / "small.mp4"
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(full), "-vf", "scale=320:180",
                    "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(small)], check=True)
    look = take_zone_look([str(WIDE)], {str(WIDE): TakeMatte(subject=str(small), skin=str(small))})
    assert look.subject.mean_l > 70 and look.background.mean_l < 25


def test_a_take_without_a_matte_is_not_read():
    assert take_zone_look([str(WIDE)], {}) is None


def test_a_reference_is_read_through_its_parts():
    look = reference_zone_look(WIDE, TIMES, parts=ellipse_parts)
    assert look.subject.mean_l > 70 and look.background.mean_l < 25
    assert look.skin is not None


def test_a_reference_whose_person_is_tiny_has_no_zones():
    assert reference_zone_look(WIDE, TIMES, parts=tiny_parts) is None
