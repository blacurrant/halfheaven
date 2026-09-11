"""What the fingerprint must get right, and what it must refuse to guess.

The failures worth guarding here are not crashes - they are confident wrong
answers. A detector that reports a caption style it never saw, or a grade
measured from a title card, does more damage than one that returns nothing,
because everything downstream treats it as fact. So most of these tests assert
that a measurement is ABSENT, or that a decoy does not read as the real thing.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest
from PIL import Image

from halfheaven.analyze.fingerprint import (
    Confidence,
    Reading,
    _dominant_hue,
    _glyphs,
    _modal_share,
    _text_masks,
)


def _canvas(width: int = 720, height: int = 1280, fill: int = 40) -> np.ndarray:
    return np.full((height, width, 3), fill, np.uint8)


def _write(image: np.ndarray, text: str, origin: tuple[int, int], scale: float = 3.0,
           colour: tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, colour, 6, cv2.LINE_AA)
    return image


# --------------------------------------------------------------------------
# Reading: absence is a finding, not a default
# --------------------------------------------------------------------------


def test_an_absent_reading_is_falsy_so_it_cannot_be_used_by_accident():
    assert not Reading.absent("nothing to see")
    assert Reading(0.0)  # a measured zero is still a measurement


def test_an_absent_reading_keeps_no_value():
    assert Reading.absent("no text").value is None


# --------------------------------------------------------------------------
# glyph detection: type behaves differently from everything else that is bright
# --------------------------------------------------------------------------


def test_a_row_of_letters_is_found():
    frame = _write(_canvas(), "HELLO", (90, 640))
    mask, heights, _labels, _kept = _glyphs(*_text_masks(frame))
    assert mask.sum() > 0
    assert len(heights) >= 3


def test_a_bright_blob_is_not_text():
    """A white balaclava, a blown highlight, a sheet of paper - all bright."""
    frame = _canvas()
    cv2.circle(frame, (360, 640), 150, (255, 255, 255), -1)
    mask, _, _labels, _kept = _glyphs(*_text_masks(frame))
    assert mask.sum() == 0


def test_a_blown_out_sky_is_not_text():
    frame = _canvas()
    frame[:500, :] = 250
    mask, _, _labels, _kept = _glyphs(*_text_masks(frame))
    assert mask.sum() == 0


def test_scattered_marks_that_share_no_baseline_are_not_text():
    """Knitted texture makes many small bright shapes. Type makes rows."""
    frame = _canvas()
    rng = np.random.default_rng(0)
    for _ in range(60):
        x, y = rng.integers(60, 660), rng.integers(200, 1100)
        cv2.circle(frame, (int(x), int(y)), 9, (255, 255, 255), -1)
    mask, _, _labels, _kept = _glyphs(*_text_masks(frame))
    assert mask.sum() == 0


def test_glyph_height_tracks_the_type_size():
    small = _write(_canvas(), "HELLO", (90, 640), scale=2.0)
    large = _write(_canvas(), "HELLO", (90, 700), scale=5.0)
    _, small_heights, _l1, _k1 = _glyphs(*_text_masks(small))
    _, large_heights, _l2, _k2 = _glyphs(*_text_masks(large))
    assert np.median(large_heights) > np.median(small_heights) * 1.5


# --------------------------------------------------------------------------
# graphics vs photography: the distinction the grade depends on
# --------------------------------------------------------------------------


def test_a_flat_colour_card_reads_as_a_graphic():
    card = cv2.resize(np.full((1280, 720, 3), (10, 0, 72), np.uint8), (240, 426))
    assert _modal_share(card) > 0.45


def test_photographic_noise_does_not_read_as_a_graphic():
    rng = np.random.default_rng(1)
    photo = rng.integers(0, 255, (426, 240, 3), dtype=np.uint8)
    assert _modal_share(photo) < 0.45


def test_a_clear_sky_is_still_photography():
    """Frame variance would call this flat. It is not a title card, and
    grading a reference must learn from its sky, not discard it."""
    sky = np.zeros((426, 240, 3), np.uint8)
    gradient = np.linspace(150, 235, 426).astype(np.uint8)
    sky[:, :, 0] = gradient[:, None]
    sky[:, :, 1] = (gradient - 20)[:, None]
    sky[:, :, 2] = (gradient - 50)[:, None]
    assert _modal_share(sky) < 0.45


# --------------------------------------------------------------------------
# accent colour: a deliberate one is concentrated; scenery is not
# --------------------------------------------------------------------------


def test_a_consistent_accent_colour_is_reported():
    red = np.tile(np.array([20, 10, 180], np.uint8), (4000, 1))
    assert _dominant_hue([red]).confidence is not Confidence.ABSENT


def test_saturated_scenery_is_refused_rather_than_averaged():
    """A red chair and a blue mug must not average into a brand colour."""
    rng = np.random.default_rng(2)
    spread = rng.integers(0, 255, (8000, 3), dtype=np.uint8)
    assert _dominant_hue([spread]).confidence is Confidence.ABSENT


def test_no_accent_pixels_at_all_is_absent_not_black():
    assert _dominant_hue([]).confidence is Confidence.ABSENT


# --------------------------------------------------------------------------
# depth: the shot-selection bias that hid the effect we were looking for
# --------------------------------------------------------------------------


def test_shots_are_ranked_by_dwell_not_by_how_big_the_text_looks():
    """Occlusion shrinks the visible text, so ranking by area puts the shots
    that use the effect last - which is how the real one got discarded."""
    from halfheaven.analyze.depth import _candidate_shots
    from halfheaven.analyze.fingerprint import FrameStats
    from halfheaven.analyze.shots import Shot

    def frame(t: float, box) -> FrameStats:
        return FrameStats(t=t, mean_rgb=(0, 0, 0), modal_share=0.1, graphic=False,
                          text_area=0.02, text_centroid=(0.5, 0.5), text_bbox=box,
                          accent_share=0.0, glyph_height=0.03, stroke_width=0.004,
                          stroke_modulation=0.2, slant=0.0, motion=0.0, zoom=0.0)

    shots = [Shot(start=0.0, end=1.0), Shot(start=1.0, end=3.0)]
    # A big caption held briefly, against a part-hidden one held far longer.
    stats = [frame(0.1 * i, (0.0, 0.0, 1.0, 1.0)) for i in range(9)]
    stats += [frame(1.0 + 0.02 * i, (0.3, 0.4, 0.7, 0.6)) for i in range(60)]

    assert _candidate_shots(stats, shots)[0].start == pytest.approx(1.0)


def _depth_frame(occluded: bool) -> tuple[np.ndarray, np.ndarray]:
    """A word crossing a subject, drawn either behind them or over them.

    The word has to be long enough to keep several letters on each side of the
    silhouette. That is not a convenience of the fixture: glyph detection wants
    letters to be adjacent, so a *short* word bitten clean in half stops
    looking like type at all, and the effect goes unmeasured. Real uses of this
    effect set the word large and wide, which is why it holds up in practice.
    """
    frame = _canvas(fill=30)
    _write(frame, "BEHIND THE SUBJECT", (20, 660), scale=1.8)
    subject = np.zeros((1280, 720), np.uint8)
    subject[400:900, 300:370] = 255
    if occluded:
        frame[400:900, 300:370] = 30       # the subject covers those letters
    return frame, subject


class _FakeSegmenter:
    """Stands in for SAM2 so the measurement is testable without a checkpoint."""

    def __init__(self, mask: np.ndarray) -> None:
        self._mask = mask

    def masks_for_video(self, video, size):
        while True:
            yield self._mask


@pytest.mark.parametrize("occluded, expected", [(True, True), (False, False)])
def test_depth_tells_text_behind_a_subject_from_text_over_them(tmp_path, occluded, expected):
    from halfheaven.analyze.depth import measure_depth
    from halfheaven.analyze.fingerprint import FrameStats
    from halfheaven.analyze.shots import Shot
    from halfheaven.media.ffmpeg_bin import ffmpeg
    import subprocess

    frame, subject = _depth_frame(occluded)
    frames_dir = tmp_path / "f"
    frames_dir.mkdir()
    for index in range(20):
        cv2.imwrite(str(frames_dir / f"{index:05d}.png"), frame)
    clip = tmp_path / "clip.mp4"
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-framerate", "30",
                    "-i", str(frames_dir / "%05d.png"), "-pix_fmt", "yuv420p", str(clip)],
                   check=True, capture_output=True)

    stats = [
        FrameStats(t=i / 30, mean_rgb=(30, 30, 30), modal_share=0.2, graphic=False,
                   text_area=0.02, text_centroid=(0.5, 0.5), text_bbox=(0.05, 0.45, 0.95, 0.55),
                   accent_share=0.0, glyph_height=0.05, stroke_width=0.005,
                   stroke_modulation=0.2, slant=0.0, motion=0.0, zoom=0.0)
        for i in range(20)
    ]
    result = measure_depth(clip, stats, [Shot(start=0.0, end=0.66)], 30.0,
                           segmenter=_FakeSegmenter(subject))
    assert result.behind_subject.value is expected


def test_depth_says_nothing_when_the_text_merely_sits_beside_the_subject(tmp_path):
    """The bug this guards: a caption next to someone has none of its ink on
    them, which looks exactly like perfect occlusion unless you check that the
    word actually continues past them."""
    from halfheaven.analyze.depth import measure_depth
    from halfheaven.analyze.fingerprint import FrameStats
    from halfheaven.analyze.shots import Shot
    from halfheaven.media.ffmpeg_bin import ffmpeg
    import subprocess

    frame = _canvas(fill=30)
    _write(frame, "ASIDE", (30, 1150), scale=2.5)      # bottom left
    subject = np.zeros((1280, 720), np.uint8)
    subject[300:1200, 430:660] = 255                    # standing to the right

    frames_dir = tmp_path / "f"
    frames_dir.mkdir()
    for index in range(20):
        cv2.imwrite(str(frames_dir / f"{index:05d}.png"), frame)
    clip = tmp_path / "clip.mp4"
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-framerate", "30",
                    "-i", str(frames_dir / "%05d.png"), "-pix_fmt", "yuv420p", str(clip)],
                   check=True, capture_output=True)

    stats = [
        FrameStats(t=i / 30, mean_rgb=(30, 30, 30), modal_share=0.2, graphic=False,
                   text_area=0.02, text_centroid=(0.3, 0.9), text_bbox=(0.02, 0.85, 0.95, 0.95),
                   accent_share=0.0, glyph_height=0.04, stroke_width=0.004,
                   stroke_modulation=0.2, slant=0.0, motion=0.0, zoom=0.0)
        for i in range(20)
    ]
    result = measure_depth(clip, stats, [Shot(start=0.0, end=0.66)], 30.0,
                           segmenter=_FakeSegmenter(subject))
    assert result.behind_subject.value is not True


# --------------------------------------------------------------------------
# striding must change the cost, never the answer
# --------------------------------------------------------------------------


def test_striding_does_not_move_the_measurements(tmp_path):
    """Sampling every nth frame is an optimisation, so it must be invisible.

    The bug this guards shipped silently: the grade seeked by `t * fps` with
    the *sampled* rate, so a strided scan read colour from the wrong part of
    the file and swung a* by 15 units while still reporting "60 photographic
    frames". Nothing about the output looked wrong.
    """
    import subprocess

    from halfheaven.analyze.fingerprint import extract_fingerprint
    from halfheaven.media.ffmpeg_bin import ffmpeg

    frames = tmp_path / "f"
    frames.mkdir()
    # First half deep red, second half pale blue: any drift in where the grade
    # samples from shows up immediately as a different mean.
    rng = np.random.default_rng(7)
    for index in range(90):
        base = np.array((40, 20, 160) if index < 45 else (200, 170, 120), np.int16)
        # Grain, so these read as photography rather than as title cards -
        # a flat plate is deliberately excluded from the grade.
        noise = rng.integers(-26, 27, (1280, 720, 3), dtype=np.int16)
        frame = np.clip(base + noise, 0, 255).astype(np.uint8)
        _write(frame, f"CARD {index // 10}", (60, 700), scale=2.5)
        cv2.imwrite(str(frames / f"{index:05d}.png"), frame)
    clip = tmp_path / "clip.mp4"
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-framerate", "30",
                    "-i", str(frames / "%05d.png"), "-pix_fmt", "yuv420p", str(clip)],
                   check=True, capture_output=True)

    one = extract_fingerprint(clip, stride=1)
    three = extract_fingerprint(clip, stride=3)

    assert one.grade.lab_mean.value is not None
    for index, channel in enumerate("Lab"):
        assert abs(one.grade.lab_mean.value[index] - three.grade.lab_mean.value[index]) < 4.0, (
            f"grade channel {channel} moved with the stride"
        )
    assert abs(one.text.duty_cycle.value - three.text.duty_cycle.value) < 0.12


# --------------------------------------------------------------------------
# type character: lean, and the face we answer with
# --------------------------------------------------------------------------


def test_an_italic_leans_and_a_roman_does_not():
    """Without this the editorial italic in a reference comes back upright."""
    from PIL import Image, ImageDraw

    from halfheaven.analyze.fingerprint import _slant
    from halfheaven.render.fonts import load_face

    def lean(file: str) -> float:
        image = Image.new("RGB", (720, 1280), (20, 20, 20))
        ImageDraw.Draw(image).text((40, 560), "Handling", font=load_face(file, 150, 700),
                                   fill=(255, 255, 255))
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        mask, _, labels, kept = _glyphs(*_text_masks(frame))
        return _slant(mask, labels, kept)

    assert lean("PlayfairDisplay-Italic.ttf") > 0.12
    assert lean("Montserrat-Italic.ttf") > 0.12
    assert abs(lean("PlayfairDisplay.ttf")) < 0.06
    assert abs(lean("Montserrat.ttf")) < 0.06


def test_measured_character_picks_a_face_of_that_character():
    from halfheaven.render.fonts import choose

    # A high-contrast lean is an editorial italic, not "the serif we have".
    editorial = choose(contrast=0.62, italic=True)
    assert editorial.italic and editorial.genre == "serif"

    flat = choose(contrast=0.08, italic=False)
    assert not flat.italic and flat.genre in ("sans", "display")

    # High contrast plus a lean is an editorial italic, not a wedding script.
    # Scripts connect their letters, so the glyph filter barely sees them and
    # their measured contrast cannot be trusted to compete on: they have to be
    # asked for by name.
    assert choose(contrast=0.85, italic=True).genre == "serif"
    assert choose(contrast=0.30, italic=True, genre="script").genre == "script"


def test_emphasis_crosses_genre_rather_than_getting_bigger():
    """A Bebas body with an Anton punch reads as the same font, louder."""
    from halfheaven.render.fonts import choose, counterpart

    body = choose(contrast=0.08, italic=False)
    assert counterpart(body).genre != body.genre


def test_every_caption_can_sit_somewhere_different(tmp_path):
    """The bug this guards made the renderer a subtitle machine: it read the
    anchor off the *style*, so every card in a program landed in one band no
    matter what the planner decided."""
    from halfheaven.render.captions import render_frame
    from halfheaven.render.caption_frames import CaptionFrame
    from halfheaven.schemas import Canvas, CaptionProfile, TextRun

    canvas = Canvas(width=360, height=640, fps=30)
    profile = CaptionProfile(present=True, size_pct=0.07, anchor=(0.5, 0.8))
    frame = CaptionFrame(runs=[TextRun(text="HERE")], duration=1.0)

    def ink_row(anchor):
        out = render_frame(frame, canvas, profile, tmp_path / f"{anchor[1]}.png", anchor=anchor)
        alpha = np.array(Image.open(out))[:, :, 3]
        rows = np.nonzero(alpha.any(axis=1))[0]
        return float(rows.mean())

    high, low = ink_row((0.5, 0.25)), ink_row((0.5, 0.75))
    assert low - high > canvas.height * 0.35, "the anchor did not move the card"
