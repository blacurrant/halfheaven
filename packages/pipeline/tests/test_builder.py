"""Building an EditProgram from editorial decisions.

This is the deterministic half of planning. The LLM contributes word indices
and nothing else; every number in the resulting program is computed here, so
this is where a timing bug would live.
"""
import pytest

from halfheaven.groq.asr import Transcript
from halfheaven.models import Word
from halfheaven.plan.builder import CaptionChunk, Decisions, build_program
from halfheaven.schemas import Canvas, CaptionProfile, MusicProfile, PunchProfile, SfxProfile, StyleProfile

CANVAS = Canvas(width=1080, height=1920, fps=30)

# 11 words, 0.02s -> 2.66s
TRANSCRIPT = Transcript(
    words=[
        Word("So", 0.02, 0.20), Word("the", 0.20, 0.36), Word("thing", 0.36, 0.58),
        Word("is,", 0.58, 0.90), Word("UM,", 0.90, 1.56), Word("I", 1.56, 1.68),
        Word("was", 1.68, 1.84), Word("I", 1.84, 1.96), Word("was", 1.96, 2.12),
        Word("gonna", 2.12, 2.34), Word("say", 2.34, 2.66),
    ],
    duration=2.66,
)


def build(profile=None, **decision_kwargs):
    return build_program(
        source="take.mp4",
        canvas=CANVAS,
        transcript=TRANSCRIPT,
        profile=profile or StyleProfile(),
        decisions=Decisions(**decision_kwargs),
    )


def test_no_cuts_produces_a_single_clip():
    program = build()
    assert len(program.video) == 1
    assert program.video[0].start == pytest.approx(0.02)
    assert program.video[0].end == pytest.approx(2.66)


def test_each_kept_span_becomes_its_own_clip():
    assert len(build(cuts=[(4, 5)]).video) == 2


def test_program_duration_excludes_the_cut_material():
    # removing "UM," (0.90-1.56) takes 0.66s off a 2.64s span
    assert build(cuts=[(4, 5)]).duration == pytest.approx(2.64 - 0.66, abs=0.01)


def test_caption_is_placed_on_the_program_timeline_not_the_source():
    # after cutting words 4-8, word 9 ("gonna") starts at source 2.12 but
    # program 0.88 + (2.12-1.96)... it must not be placed at 2.12
    program = build(cuts=[(4, 9)], caption_chunks=[CaptionChunk(word_indices=[9, 10])])
    assert program.captions[0].t == pytest.approx(0.88, abs=0.01)


def test_caption_text_joins_its_words():
    program = build(caption_chunks=[CaptionChunk(word_indices=[2, 3])])
    assert program.captions[0].plain_text == "thing is,"


def test_caption_whose_words_were_all_cut_is_dropped():
    # the chunk covers exactly the removed stutter, so it has nowhere to go
    program = build(cuts=[(5, 9)], caption_chunks=[CaptionChunk(word_indices=[5, 6, 7, 8])])
    assert program.captions == []


def test_caption_uses_the_profile_anchor_and_animation():
    profile = StyleProfile(captions=CaptionProfile(present=True, anchor=(0.5, 0.80), anim="fade"))
    program = build(profile=profile, caption_chunks=[CaptionChunk(word_indices=[0])])
    assert program.captions[0].anchor == (0.5, 0.80)
    assert program.captions[0].anim == "fade"


def test_punch_in_scales_the_clip_that_contains_the_word():
    profile = StyleProfile(punch=PunchProfile(rate=1.0, scale_mean=1.18))
    program = build(profile=profile, cuts=[(4, 5)], punch_word_indices=[9])
    assert program.video[1].scale_to == pytest.approx(1.18)
    assert program.video[0].scale_to is None


def test_sfx_lands_on_every_cut_when_the_reference_always_uses_one():
    profile = StyleProfile(sfx=SfxProfile(rate_at_cuts=1.0, families=["whoosh"]))
    program = build(profile=profile, cuts=[(4, 5), (7, 9)])
    # two cuts create three clips -> two internal seams
    assert len(program.sfx) == 2
    assert {hit.family for hit in program.sfx} == {"whoosh"}


def test_no_sfx_when_the_reference_never_uses_one():
    assert build(cuts=[(4, 5)]).sfx == []


def test_music_bed_is_carried_over_when_the_reference_has_one():
    profile = StyleProfile(music=MusicProfile(present=True, gain_db=-16.0, duck_db=-8.0))
    program = build(profile=profile, music_src="bed.mp3")
    assert program.music.gain_db == pytest.approx(-16.0)
    assert program.music.duck_db == pytest.approx(-8.0)


# --- word-level captions ------------------------------------------------------
# Captions carry one run per word, timed from Whisper, so the renderer can
# reveal them one at a time and style individual words differently.


def test_each_caption_word_becomes_its_own_run():
    program = build(caption_chunks=[CaptionChunk(word_indices=[0, 1, 2])])
    assert [run.text for run in program.captions[0].runs] == ["So", "the", "thing"]


def test_each_run_carries_its_own_program_time():
    # program time, not source time: the first kept word sits at 0.0 even
    # though it starts at 0.02 in the source
    program = build(caption_chunks=[CaptionChunk(word_indices=[0, 1, 2])])
    times = [run.t for run in program.captions[0].runs]
    assert times == pytest.approx([0.0, 0.18, 0.34], abs=0.01)


def test_run_times_are_shifted_by_earlier_cuts():
    # drop words 4-8, so word 9 lands earlier in the program than in the source
    program = build(cuts=[(4, 9)], caption_chunks=[CaptionChunk(word_indices=[9, 10])])
    assert program.captions[0].runs[0].t == pytest.approx(0.88, abs=0.01)


def test_a_caption_of_several_words_reveals_word_by_word():
    program = build(caption_chunks=[CaptionChunk(word_indices=[0, 1, 2])])
    assert program.captions[0].reveals_word_by_word is True


def test_an_emphasised_word_gets_the_emphasis_style():
    program = build(
        caption_chunks=[CaptionChunk(word_indices=[0, 1, 2])],
        emphasis_word_indices=[1],
    )
    assert [run.style for run in program.captions[0].runs] == ["default", "emphasis", "default"]


def test_words_without_emphasis_all_use_the_body_style():
    program = build(caption_chunks=[CaptionChunk(word_indices=[0, 1])])
    assert {run.style for run in program.captions[0].runs} == {"default"}


def test_cut_words_never_appear_as_runs():
    program = build(cuts=[(1, 2)], caption_chunks=[CaptionChunk(word_indices=[0, 1, 2])])
    assert [run.text for run in program.captions[0].runs] == ["So", "thing"]
