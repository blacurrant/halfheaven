"""Source-time -> program-time mapping.

After cutting, a moment in the source lands somewhere else in the finished
video. Captions, SFX and punch-ins are all placed on the *program* timeline,
so every one of them depends on this being exact.
"""
import pytest

from halfheaven.plan.timeline import Timeline

# Two kept spans: 0.02-0.90 (0.88s) and 1.56-2.66 (1.10s). Total 1.98s.
SPANS = [(0.02, 0.90), (1.56, 2.66)]


def test_duration_is_the_sum_of_kept_spans():
    assert Timeline(SPANS).duration == pytest.approx(1.98)


def test_start_of_first_span_maps_to_zero():
    assert Timeline(SPANS).to_program(0.02) == pytest.approx(0.0)


def test_time_inside_the_first_span_keeps_its_offset():
    assert Timeline(SPANS).to_program(0.50) == pytest.approx(0.48)


def test_start_of_second_span_lands_immediately_after_the_first():
    assert Timeline(SPANS).to_program(1.56) == pytest.approx(0.88)


def test_time_inside_the_second_span_accounts_for_the_removed_gap():
    assert Timeline(SPANS).to_program(2.00) == pytest.approx(1.32)


def test_time_inside_a_removed_gap_has_no_program_position():
    assert Timeline(SPANS).to_program(1.20) is None


def test_time_before_the_first_span_has_no_program_position():
    assert Timeline(SPANS).to_program(0.00) is None
