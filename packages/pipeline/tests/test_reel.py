"""Several clips treated as one take.

Uploading three takes should behave like uploading one long one: the transcript
runs straight through, cuts land wherever they land, and the renderer is told
which file each piece came from. The join is bookkeeping, and it belongs in one
place rather than smeared through the planner.
"""
import pytest

from halfheaven.plan.reel import Reel


def reel():
    return Reel([("a.mp4", 10.0), ("b.mp4", 5.0), ("c.mp4", 8.0)])


def test_the_reel_runs_as_long_as_its_parts():
    assert reel().duration == pytest.approx(23.0)


def test_a_moment_early_on_belongs_to_the_first_clip():
    assert reel().locate(3.0) == ("a.mp4", pytest.approx(3.0))


def test_a_moment_maps_back_into_its_own_clip_s_clock():
    assert reel().locate(12.0) == ("b.mp4", pytest.approx(2.0))


def test_a_moment_in_the_last_clip_maps_too():
    assert reel().locate(20.0) == ("c.mp4", pytest.approx(5.0))


def test_a_moment_past_the_end_clamps_to_the_last_frame():
    source, at = reel().locate(99.0)
    assert source == "c.mp4" and at == pytest.approx(8.0)


# --- splitting ----------------------------------------------------------------

def test_a_span_inside_one_clip_stays_whole():
    assert reel().split((2.0, 6.0)) == [("a.mp4", pytest.approx(2.0), pytest.approx(6.0))]


def test_a_span_crossing_a_join_is_split_at_the_boundary():
    got = reel().split((8.0, 12.0))
    assert got == [("a.mp4", pytest.approx(8.0), pytest.approx(10.0)),
                   ("b.mp4", pytest.approx(0.0), pytest.approx(2.0))]


def test_a_span_crossing_two_joins_yields_three_pieces():
    assert len(reel().split((8.0, 17.0))) == 3


def test_split_pieces_add_up_to_the_original_length():
    pieces = reel().split((8.0, 17.0))
    assert sum(e - s for _, s, e in pieces) == pytest.approx(9.0)


def test_a_zero_length_span_yields_nothing():
    assert reel().split((5.0, 5.0)) == []


def test_a_span_past_the_end_is_clipped_to_what_exists():
    pieces = reel().split((20.0, 99.0))
    assert sum(e - s for _, s, e in pieces) == pytest.approx(3.0)


# --- one clip behaves as before -----------------------------------------------

def test_a_single_clip_reel_is_a_passthrough():
    one = Reel([("only.mp4", 12.0)])
    assert one.split((2.0, 7.0)) == [("only.mp4", pytest.approx(2.0), pytest.approx(7.0))]


def test_an_empty_reel_has_no_duration():
    assert Reel([]).duration == 0.0
