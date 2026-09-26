"""Measuring what a grade does at the matte edge and over time."""
import numpy as np
import pytest

from halfheaven.analyze.grade_eval import flicker, seam


def edge_scene():
    lightness = np.full((568, 100), 20.0, np.float32)
    lightness[:, :50] = 60.0
    alpha = np.zeros((568, 100), np.float32)
    alpha[:, :50] = 1.0
    return lightness, alpha


def test_a_clean_edge_has_no_seam():
    lightness, alpha = edge_scene()
    assert seam(lightness, alpha) == pytest.approx(0.0, abs=0.5)


def test_a_bright_rim_reads_positive_and_a_dark_line_negative():
    lightness, alpha = edge_scene()
    rim, line = lightness.copy(), lightness.copy()
    rim[:, 50:52] = 90.0         # just outside the subject: a glow on the wall
    line[:, 48:50] = 0.0         # just inside: a dark outline on the hair
    assert seam(rim, alpha) > 3.0
    assert seam(line, alpha) < -3.0


def test_flicker_is_what_the_grade_adds_over_the_footage():
    raw = [np.full((60, 60), 30.0, np.float32) for _ in range(6)]
    steady = [frame.copy() for frame in raw]
    pumping = [frame + (3.0 if k % 2 else 0.0) for k, frame in enumerate(raw)]
    alphas = [np.zeros((60, 60), np.float32)] * 6
    skins = [np.zeros((60, 60), np.float32)] * 6
    assert flicker(steady, raw, alphas, skins)["room"] == pytest.approx(0.0)
    assert flicker(pumping, raw, alphas, skins)["room"] == pytest.approx(3.0)
    assert flicker(steady, raw, alphas, skins)["face"] is None


from halfheaven.analyze.grade_eval import evaluate_pair, verdict
from halfheaven.analyze.segment import write_matte_video
from halfheaven.analyze.zones import summarise
from halfheaven.schemas import TakeMatte
from tests.zone_fakes import WIDE, Bright, make_look


def fake_fingerprint():
    look = make_look(subject_l=60.0, background_l=40.0, skin_l=70.0, skin_ab=(12.0, 18.0))
    reading = lambda value: {"value": value, "confidence": "measured", "note": ""}
    return {"source": "fake.mp4",
            "grade": {"lab_mean": reading([35.0, 6.0, 4.0]), "lab_std": reading([15.0, 8.0, 9.0]),
                      **{name: reading(value) for name, value in summarise(look).items()}},
            "zone_look": look.model_dump()}


def test_a_pair_is_rendered_both_ways_and_measured(tmp_path):
    matte = write_matte_video(WIDE, Bright(), tmp_path / "m.mp4", feather=0)
    report = evaluate_pair(str(WIDE), TakeMatte(subject=str(matte), skin=str(matte)),
                           fake_fingerprint(), tmp_path / "pair")
    assert (tmp_path / "pair" / "today.mp4").exists() and (tmp_path / "pair" / "colourist.mp4").exists()
    assert report["colourist"]["background_l"] > report["raw"]["background_l"] + 5
    assert {"seam", "flicker_room", "flicker_face", "face_l_change", "render_seconds"} <= set(report["colourist"])
    assert verdict([report])["fallback_pairs"] == []


def test_a_matte_left_half_written_by_a_crashed_run_is_not_reused(tmp_path):
    from halfheaven.analyze.grade_eval import _usable_matte

    whole = write_matte_video(WIDE, Bright(), tmp_path / "whole.mp4", feather=0)
    stub = tmp_path / "stub.mp4"
    stub.write_bytes(whole.read_bytes()[:261])      # what an interrupted writer leaves
    assert _usable_matte(whole, str(WIDE))
    assert not _usable_matte(stub, str(WIDE))


def test_a_reference_without_zones_is_scored_as_a_fallback(tmp_path):
    matte = write_matte_video(WIDE, Bright(), tmp_path / "m.mp4", feather=0)
    fingerprint = fake_fingerprint()
    fingerprint.pop("zone_look")
    report = evaluate_pair(str(WIDE), TakeMatte(subject=str(matte), skin=str(matte)), fingerprint, tmp_path / "pair")
    assert "colourist" not in report and "today" in report
    assert verdict([report])["fallback_pairs"] == [f"{WIDE} x fake.mp4"]
