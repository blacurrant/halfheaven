"""Giving a single locked-off take some visual rhythm.

A talking head shot on one camera has no cuts to inherit. Holding one framing
for a minute is what made the output read as a static clip with subtitles, so
consecutive segments are reframed - wide, medium, punched - and the reframe
becomes the cut.
"""
import pytest

from halfheaven.groq.asr import Transcript
from halfheaven.models import Word
from halfheaven.plan.builder import Decisions, build_program
from halfheaven.schemas import Canvas, PacingProfile, PunchProfile, StyleProfile

CANVAS = Canvas(width=1080, height=1920, fps=30)

# 24 words with a pause every 4th, so silence compression makes several clips
WORDS = []
t = 0.0
for i in range(24):
    WORDS.append(Word(f"w{i}", t, t + 0.28))
    t += 0.3 + (0.9 if i % 4 == 3 else 0.0)
TRANSCRIPT = Transcript(words=WORDS, duration=t)


def build(profile=None, **kw):
    return build_program(
        source="take.mp4", canvas=CANVAS, transcript=TRANSCRIPT,
        profile=profile or StyleProfile(), decisions=Decisions(**kw))


def scales(program):
    return [c.scale_to or 1.0 for c in program.video]


def test_the_take_is_split_into_several_segments():
    assert len(build().video) >= 4


def test_neighbouring_segments_may_share_a_framing():
    # holding across short segments is the point: a framing that changes on
    # every silence twitches rather than cuts
    got = scales(build(profile=StyleProfile(punch=PunchProfile(variety=1.0))))
    assert any(a == b for a, b in zip(got, got[1:])), got


def test_the_framing_still_changes_over_the_video():
    got = scales(build(profile=StyleProfile(punch=PunchProfile(variety=1.0))))
    assert len(set(got)) >= 2, got


def test_variety_off_leaves_every_segment_wide():
    program = build(profile=StyleProfile(punch=PunchProfile(variety=0.0)))
    assert set(scales(program)) == {1.0}


def test_variety_uses_more_than_one_framing():
    program = build(profile=StyleProfile(punch=PunchProfile(variety=1.0)))
    assert len(set(scales(program))) >= 2


def test_a_stressed_word_gets_the_tightest_framing_in_its_segment():
    program = build(profile=StyleProfile(punch=PunchProfile(variety=1.0)),
                    punch_word_indices=[9])
    target = [i for i, c in enumerate(program.video)
              if c.start <= WORDS[9].start <= c.end]
    assert target, "no segment holds that word"
    assert scales(program)[target[0]] == max(scales(program))


def test_every_crop_centre_stays_inside_the_frame():
    program = build(profile=StyleProfile(punch=PunchProfile(variety=1.0)))
    assert all(0.0 <= c.crop_x <= 1.0 for c in program.video)


def test_framing_is_deterministic_for_the_same_input():
    a = scales(build(profile=StyleProfile(punch=PunchProfile(variety=1.0))))
    b = scales(build(profile=StyleProfile(punch=PunchProfile(variety=1.0))))
    assert a == b


def test_a_reframe_never_zooms_out_past_the_source():
    program = build(profile=StyleProfile(punch=PunchProfile(variety=1.0)))
    assert min(scales(program)) >= 1.0


# --- how often it changes -----------------------------------------------------
# Sixteen reframes in fifty-seven seconds reads as nervous, not paced. How long
# to hold a framing is not a guess: the reference already told us how long it
# holds a shot, and that measurement was being ignored.


def changes(program):
    got = scales(program)
    return sum(1 for a, b in zip(got, got[1:]) if a != b)


def calm(median_shot):
    return StyleProfile(punch=PunchProfile(variety=1.0),
                        pacing=PacingProfile(median_shot=median_shot, cuts_per_min=60 / median_shot))


def test_a_slow_reference_reframes_less_than_a_fast_one():
    slow = changes(build(profile=calm(7.0)))
    fast = changes(build(profile=calm(1.5)))
    assert slow < fast, f"slow={slow} fast={fast}"


def test_a_slow_reference_holds_each_framing_for_a_while():
    program = build(profile=calm(7.0))
    held, current, run = [], None, 0.0
    for clip in program.video:
        key = (clip.scale_to, clip.crop_x)
        if key != current and current is not None:
            held.append(run)
            run = 0.0
        current = key
        run += clip.end - clip.start
    held.append(run)
    # every held framing except possibly the last lasts a meaningful stretch
    assert all(h >= 1.5 for h in held[:-1]), held


def test_a_stressed_word_still_tightens_even_inside_a_hold():
    program = build(profile=calm(7.0), punch_word_indices=[9])
    assert max(scales(program)) > 1.0


def test_variety_off_still_means_no_reframing():
    assert set(scales(build(profile=StyleProfile(punch=PunchProfile(variety=0.0))))) == {1.0}
