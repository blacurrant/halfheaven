"""Caption geometry from OpenCV, not from the vision model.

The live probe showed the VLM reporting x=0.28 for a dead-centre caption. It
reads style well and geometry badly, so position and colour are measured here
and only the semantic attributes are asked of the model.
"""
import pytest

from halfheaven.analyze.text_regions import detect_caption_box


def test_finds_a_caption(caption_frame):
    assert detect_caption_box(caption_frame()) is not None


def test_horizontal_centre_is_accurate(caption_frame):
    box = detect_caption_box(caption_frame())
    assert box.center_x_pct == pytest.approx(0.50, abs=0.04)


def test_vertical_position_is_accurate(caption_frame):
    # text drawn with its top at 0.72 of height, 96px tall -> centre ~0.745
    box = detect_caption_box(caption_frame())
    assert box.center_y_pct == pytest.approx(0.745, abs=0.04)


def test_reads_the_actual_fill_colour(caption_frame):
    box = detect_caption_box(caption_frame())
    assert box.fill_hex.upper() == "#FFE94A"


def test_survives_a_large_distractor_shape(caption_frame):
    box = detect_caption_box(caption_frame(distractor=True))
    assert box.center_x_pct == pytest.approx(0.50, abs=0.04)


def test_frame_with_no_caption_returns_nothing(blank_frame):
    assert detect_caption_box(blank_frame()) is None


def test_fill_is_the_glyph_colour_not_an_average_with_its_background(caption_frame):
    # Observed on real footage: sampling too low a percentile mixed the glyph
    # with its dark surround and reported muddy olive for a bright gold caption.
    box = detect_caption_box(caption_frame(fill=(255, 214, 10)))
    red, green, blue = (int(box.fill_hex[i:i+2], 16) for i in (1, 3, 5))
    assert red > 230 and green > 190 and blue < 60
