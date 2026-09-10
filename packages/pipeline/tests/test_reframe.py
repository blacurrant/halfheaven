"""Following the subject when a wide source has to become vertical.

Centre-cropping 16:9 to 9:16 throws away two thirds of the frame, so a speaker
standing off to one side simply disappears. Tracking where they are over time
is what makes horizontal footage usable at all - which is most of the footage
anyone already has.
"""
import pathlib

import pytest

from halfheaven.analyze.subject import needs_reframe, track_subject
from halfheaven.media.probe import probe
from halfheaven.schemas import Canvas

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
WIDE = FIXTURES / "wide_subject_moves.mp4"          # 640x360, subject L -> C -> R
TALL = FIXTURES / "three_shots_at_1.0_3.0.mp4"      # 320x568, already vertical

VERTICAL = Canvas(width=1080, height=1920, fps=30)
HORIZONTAL = Canvas(width=1920, height=1080, fps=30)


# --- when reframing is needed -------------------------------------------------

def test_a_wide_source_needs_reframing_for_a_vertical_canvas():
    assert needs_reframe(probe(WIDE), VERTICAL) is True


def test_an_already_vertical_source_does_not():
    assert needs_reframe(probe(TALL), VERTICAL) is False


def test_a_wide_source_into_a_wide_canvas_does_not():
    assert needs_reframe(probe(WIDE), HORIZONTAL) is False


# --- following the subject ----------------------------------------------------

def spans(n: int, length: float):
    return [(i * length, (i + 1) * length) for i in range(n)]


def test_a_track_is_returned_for_every_span():
    got = track_subject(WIDE, spans(4, 1.0))
    assert len(got) == 4


def test_every_position_is_inside_the_frame():
    assert all(0.0 <= x <= 1.0 for x in track_subject(WIDE, spans(4, 1.0)))


def test_the_track_follows_the_subject_across_the_frame():
    # the fixture puts the subject left, then centre, then right
    early, late = track_subject(WIDE, [(0.2, 1.2), (3.2, 4.2)])
    assert early < late - 0.15, f"{early:.2f} -> {late:.2f} did not follow"


def test_the_first_span_lands_left_of_centre():
    assert track_subject(WIDE, [(0.2, 1.2)])[0] < 0.45


def test_the_last_span_lands_right_of_centre():
    assert track_subject(WIDE, [(3.2, 4.2)])[0] > 0.55


def test_a_still_frame_stays_near_the_middle():
    # nothing moves in this one, so there is nothing to follow
    assert track_subject(TALL, [(0.2, 0.9)])[0] == pytest.approx(0.5, abs=0.2)


def test_tracking_is_deterministic():
    a = track_subject(WIDE, spans(4, 1.0))
    b = track_subject(WIDE, spans(4, 1.0))
    assert a == b


def test_no_spans_gives_no_track():
    assert track_subject(WIDE, []) == []
