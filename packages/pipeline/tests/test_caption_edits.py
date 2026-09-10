"""Fixing individual caption cards.

Whisper mishears things, and a wrong word on screen is the most visible flaw an
auto-caption has. A fix must not re-run the pipeline: re-transcribing would
discard the correction that prompted it. The EditProgram is the document, so an
edit patches the program and only the render repeats.
"""
import pytest
from pydantic import ValidationError

from halfheaven.plan.edits import CaptionEdit, apply_caption_edits
from halfheaven.schemas import Canvas, Caption, EditProgram, TextRun, VideoClip

CANVAS = Canvas(width=1080, height=1920, fps=30)


def program() -> EditProgram:
    return EditProgram(
        canvas=CANVAS,
        video=[VideoClip(src="a.mp4", start=0.0, end=12.0)],
        captions=[
            Caption(t=0.0, duration=1.5, runs=[
                TextRun(text="I", t=0.0), TextRun(text="phone", t=0.6), TextRun(text="mine", t=1.1)]),
            Caption(t=2.0, duration=1.2, runs=[
                TextRun(text="second", t=2.0), TextRun(text="card", t=2.6)]),
        ],
    )


def texts(prog, i=0):
    return [r.text for r in prog.captions[i].runs]


def times(prog, i=0):
    return [r.t for r in prog.captions[i].runs]


# --- correcting words ---------------------------------------------------------

def test_replacing_the_text_replaces_the_words():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, text="iPhone mine")])
    assert texts(out) == ["iPhone", "mine"]


def test_a_correction_leaves_other_cards_alone():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, text="iPhone mine")])
    assert texts(out, 1) == ["second", "card"]


def test_new_words_stay_inside_the_card_s_own_span():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, text="one two three four five")])
    card = out.captions[0]
    assert all(card.t <= r.t <= card.t + card.duration for r in card.runs)


def test_new_word_times_run_forwards():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, text="one two three four")])
    assert times(out) == sorted(times(out))


def test_the_card_keeps_its_place_on_the_timeline():
    before = program().captions[0]
    out = apply_caption_edits(program(), [CaptionEdit(index=0, text="totally different words here")])
    assert out.captions[0].t == pytest.approx(before.t)
    assert out.captions[0].duration == pytest.approx(before.duration)


def test_fewer_words_than_before_is_fine():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, text="hello")])
    assert texts(out) == ["hello"]


def test_empty_text_is_refused_rather_than_producing_a_blank_card():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, text="   ")])
    assert texts(out) == ["I", "phone", "mine"]


# --- emphasis -----------------------------------------------------------------

def test_marking_a_word_emphasises_exactly_that_word():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, emphasis=[1])])
    assert [r.style for r in out.captions[0].runs] == ["default", "emphasis", "default"]


def test_clearing_emphasis_returns_every_word_to_the_body_style():
    marked = apply_caption_edits(program(), [CaptionEdit(index=0, emphasis=[1])])
    cleared = apply_caption_edits(marked, [CaptionEdit(index=0, emphasis=[])])
    assert {r.style for r in cleared.captions[0].runs} == {"default"}


def test_emphasis_survives_a_text_correction_when_positions_still_exist():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, text="iPhone mine", emphasis=[0])])
    assert out.captions[0].runs[0].style == "emphasis"


def test_an_emphasis_index_past_the_end_is_ignored():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, emphasis=[99])])
    assert {r.style for r in out.captions[0].runs} == {"default"}


# --- removing -----------------------------------------------------------------

def test_deleting_a_card_removes_it():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, delete=True)])
    assert len(out.captions) == 1 and texts(out, 0) == ["second", "card"]


def test_deleting_every_card_leaves_a_valid_program():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, delete=True),
                                          CaptionEdit(index=1, delete=True)])
    assert out.captions == [] and out.duration > 0


# --- robustness ---------------------------------------------------------------

def test_an_edit_for_a_card_that_does_not_exist_is_ignored():
    out = apply_caption_edits(program(), [CaptionEdit(index=57, text="nope")])
    assert len(out.captions) == 2


def test_several_edits_apply_together():
    out = apply_caption_edits(program(), [
        CaptionEdit(index=0, text="iPhone mine"),
        CaptionEdit(index=1, emphasis=[0]),
    ])
    assert texts(out) == ["iPhone", "mine"]
    assert out.captions[1].runs[0].style == "emphasis"


def test_deletes_do_not_shift_the_indices_of_other_edits():
    # both edits address the program as the caller saw it
    out = apply_caption_edits(program(), [
        CaptionEdit(index=0, delete=True),
        CaptionEdit(index=1, text="renamed card"),
    ])
    assert len(out.captions) == 1 and texts(out, 0) == ["renamed", "card"]


def test_the_result_is_still_a_valid_program():
    out = apply_caption_edits(program(), [CaptionEdit(index=0, text="one two three")])
    EditProgram.model_validate(out.model_dump())
