"""Mixing a music bed under the speech.

Short-form without music feels dead, and the difficulty is not adding the track
but keeping it out of the way. The bed is compressed against the speech itself,
so it drops when someone talks and returns in the gaps, which is what ducking
means and what makes a bed sound deliberate rather than loud.
"""
import pathlib
import subprocess

import pytest

from halfheaven.media.ffmpeg_bin import ffmpeg
from halfheaven.media.probe import probe
from halfheaven.render.video import build_finish_command, render
from halfheaven.schemas import Canvas, EditProgram, MusicBed, VideoClip

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SPEECH = FIXTURES / "with_audio_track.mp4"        # 3s, has an audio track
GAPPY = FIXTURES / "speech_with_gap.mp4"          # talk, silence, talk
MUSIC = FIXTURES / "music_bed.m4a"
CANVAS = Canvas(width=320, height=568, fps=30)


def program(**over):
    base = dict(canvas=CANVAS, video=[VideoClip(src=str(SPEECH), start=0.0, end=2.5)])
    base.update(over)
    return EditProgram(**base)


def graph(command):
    return command[command.index("-filter_complex") + 1] if "-filter_complex" in command else ""


def loudness(path: pathlib.Path, start: float | None = None, length: float | None = None) -> float:
    """Loudness in dB, optionally over one window.

    Integrated loudness is the wrong instrument for judging a bed: the limiter
    on a hot mix pulls the whole programme down, so a louder bed can measure
    quieter overall. Ducking is only visible in the gaps, so the tests below
    measure the window where the speech stops.
    """
    window = ["-ss", f"{start:.2f}", "-t", f"{length:.2f}"] if start is not None else []
    out = subprocess.run(
        [ffmpeg(), "-hide_banner", *window, "-i", str(path),
         "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    line = [l for l in out.splitlines() if "mean_volume" in l]
    return float(line[-1].split("mean_volume:")[1].split("dB")[0].strip()) if line else -99.0


# --- the graph ----------------------------------------------------------------

def test_a_bed_is_ducked_against_the_speech(tmp_path):
    command = build_finish_command(
        program(music=MusicBed(src=str(MUSIC))), tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path)
    assert "sidechaincompress" in graph(command)


def test_the_bed_is_an_input(tmp_path):
    command = build_finish_command(
        program(music=MusicBed(src=str(MUSIC))), tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path)
    assert str(MUSIC) in command


def test_no_music_means_no_ducking_and_no_re_encode(tmp_path):
    command = build_finish_command(program(), tmp_path / "b.mp4", tmp_path / "o.mp4", tmp_path)
    assert "sidechaincompress" not in graph(command)
    assert "copy" in command


# --- the sound ----------------------------------------------------------------

def test_the_output_still_has_audio(tmp_path):
    out = render(program(music=MusicBed(src=str(MUSIC))), tmp_path / "o.mp4", work_dir=tmp_path)
    assert probe(out).has_audio is True


def test_the_cut_keeps_its_length_with_music(tmp_path):
    out = render(program(music=MusicBed(src=str(MUSIC))), tmp_path / "o.mp4", work_dir=tmp_path)
    assert probe(out).duration == pytest.approx(2.5, abs=0.25)


# the silent stretch in the middle of the gappy fixture
GAP_AT, GAP_FOR = 1.5, 1.0


def gappy(**over):
    base = dict(canvas=CANVAS, video=[VideoClip(src=str(GAPPY), start=0.0, end=3.8)])
    base.update(over)
    return EditProgram(**base)


def test_a_bed_fills_the_silence(tmp_path):
    plain = render(gappy(), tmp_path / "plain.mp4", work_dir=tmp_path / "a")
    mixed = render(gappy(music=MusicBed(src=str(MUSIC), gain_db=-14.0)),
                   tmp_path / "mixed.mp4", work_dir=tmp_path / "b")
    assert loudness(mixed, GAP_AT, GAP_FOR) > loudness(plain, GAP_AT, GAP_FOR) + 6


def test_a_quieter_bed_lands_quieter_in_the_gap(tmp_path):
    loud = render(gappy(music=MusicBed(src=str(MUSIC), gain_db=-10.0)),
                  tmp_path / "loud.mp4", work_dir=tmp_path / "a")
    soft = render(gappy(music=MusicBed(src=str(MUSIC), gain_db=-34.0)),
                  tmp_path / "soft.mp4", work_dir=tmp_path / "b")
    assert loudness(loud, GAP_AT, GAP_FOR) > loudness(soft, GAP_AT, GAP_FOR) + 4


def test_the_bed_is_quieter_under_speech_than_in_the_gap(tmp_path):
    # ducking, stated directly: same bed, two moments
    out = render(gappy(music=MusicBed(src=str(MUSIC), gain_db=-10.0)),
                 tmp_path / "b.mp4", work_dir=tmp_path / "a")
    plain = render(gappy(), tmp_path / "p.mp4", work_dir=tmp_path / "b")
    bed_in_gap = loudness(out, GAP_AT, GAP_FOR) - loudness(plain, GAP_AT, GAP_FOR)
    bed_under_speech = loudness(out, 0.3, 0.7) - loudness(plain, 0.3, 0.7)
    assert bed_in_gap > bed_under_speech


def test_a_missing_bed_is_skipped_rather_than_fatal(tmp_path):
    out = render(program(music=MusicBed(src=str(tmp_path / "nope.m4a"))),
                 tmp_path / "o.mp4", work_dir=tmp_path)
    assert probe(out).duration == pytest.approx(2.5, abs=0.25)
