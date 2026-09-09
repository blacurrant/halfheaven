"""The EditProgram contract.

This is the only thing the renderer ever sees. If an invalid program can be
constructed, the failure shows up as a corrupt video minutes later instead of
as an exception, so the invariants are enforced at construction time.
"""
import pytest
from pydantic import ValidationError

from halfheaven.schemas import Canvas, Caption, EditProgram, MusicBed, SfxHit, VideoClip


def clip(src="a.mp4", start=0.0, end=2.0):
    return VideoClip(src=src, start=start, end=end)


def program(**overrides):
    base = dict(canvas=Canvas(width=1080, height=1920, fps=30), video=[clip(end=2.0), clip(start=5.0, end=8.0)])
    base.update(overrides)
    return EditProgram(**base)


def test_duration_is_the_sum_of_clip_durations():
    assert program().duration == pytest.approx(5.0)


def test_clip_that_ends_before_it_starts_is_rejected():
    with pytest.raises(ValidationError):
        VideoClip(src="a.mp4", start=3.0, end=1.0)


def test_zero_length_clip_is_rejected():
    with pytest.raises(ValidationError):
        VideoClip(src="a.mp4", start=1.0, end=1.0)


def test_negative_source_time_is_rejected():
    with pytest.raises(ValidationError):
        VideoClip(src="a.mp4", start=-0.5, end=1.0)


def test_program_with_no_clips_is_rejected():
    with pytest.raises(ValidationError):
        program(video=[])


def test_caption_past_the_end_of_the_program_is_rejected():
    with pytest.raises(ValidationError):
        program(captions=[Caption(t=99.0, duration=0.4, text="late")])


def test_caption_inside_the_program_is_accepted():
    assert program(captions=[Caption(t=1.0, duration=0.4, text="ok")]).captions[0].text == "ok"


def test_sfx_past_the_end_of_the_program_is_rejected():
    with pytest.raises(ValidationError):
        program(sfx=[SfxHit(t=99.0, family="whoosh")])


def test_punch_in_scale_below_one_is_rejected():
    # a punch-in zooms in; scaling out would letterbox the frame
    with pytest.raises(ValidationError):
        VideoClip(src="a.mp4", start=0.0, end=1.0, scale_to=0.8)


def test_program_round_trips_through_json():
    original = program(captions=[Caption(t=1.0, duration=0.4, text="ok")], music=MusicBed(src="bed.mp3"))
    assert EditProgram.model_validate_json(original.model_dump_json()) == original
