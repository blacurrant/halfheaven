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


# --- following a subject ------------------------------------------------------
# On a wide source the crop centre should follow the speaker rather than drift
# on a pattern: two thirds of the frame is being discarded, and guessing wrong
# crops them out entirely.


def test_a_tracker_decides_the_crop_centre():
    program = build_program(
        source="take.mp4", canvas=CANVAS, transcript=TRANSCRIPT,
        profile=StyleProfile(punch=PunchProfile(variety=1.0)),
        decisions=Decisions(),
        tracker=lambda spans: [0.25] * len(spans),
    )
    assert all(c.crop_x == pytest.approx(0.25) for c in program.video)


def test_the_tracker_sees_every_span():
    seen = {}
    build_program(
        source="take.mp4", canvas=CANVAS, transcript=TRANSCRIPT,
        profile=StyleProfile(), decisions=Decisions(),
        tracker=lambda spans: seen.setdefault("n", len(spans)) and [0.5] * len(spans)
                              or [0.5] * len(spans),
    )
    assert seen["n"] >= 4


def test_without_a_tracker_the_pattern_still_applies():
    program = build(profile=StyleProfile(punch=PunchProfile(variety=1.0)))
    assert len({c.crop_x for c in program.video}) >= 1


def test_a_short_track_does_not_break_the_build():
    program = build_program(
        source="take.mp4", canvas=CANVAS, transcript=TRANSCRIPT,
        profile=StyleProfile(), decisions=Decisions(),
        tracker=lambda spans: [0.3],           # fewer than there are spans
    )
    assert all(0.0 <= c.crop_x <= 1.0 for c in program.video)


# --- several takes ------------------------------------------------------------
# A cut does not care where one take ends and the next begins, but the renderer
# can only read one file at a time.

from halfheaven.plan.reel import Reel  # noqa: E402


def test_clips_name_the_file_each_piece_came_from():
    program = build_program(
        source="unused.mp4", canvas=CANVAS, transcript=TRANSCRIPT,
        profile=StyleProfile(), decisions=Decisions(),
        reel=Reel([("a.mp4", 3.0), ("b.mp4", 20.0)]),
    )
    assert {c.src for c in program.video} == {"a.mp4", "b.mp4"}


def test_a_span_crossing_a_join_becomes_two_clips():
    # the join at 3.0s falls inside a kept span; a join landing in a trimmed
    # pause would correctly split nothing
    program = build_program(
        source="unused.mp4", canvas=CANVAS, transcript=TRANSCRIPT,
        profile=StyleProfile(), decisions=Decisions(),
        reel=Reel([("a.mp4", 3.0), ("b.mp4", 20.0)]),
    )
    # more clips than spans means at least one span was split at the boundary
    assert len(program.video) > len(build().video)


def test_both_halves_of_a_split_share_one_framing():
    program = build_program(
        source="unused.mp4", canvas=CANVAS, transcript=TRANSCRIPT,
        profile=StyleProfile(punch=PunchProfile(variety=1.0)), decisions=Decisions(),
        reel=Reel([("a.mp4", 3.0), ("b.mp4", 20.0)]),
    )
    joined = [c for c in program.video if c.src == "a.mp4"][-1]
    following = [c for c in program.video if c.src == "b.mp4"][0]
    assert (joined.scale_to, joined.crop_x) == (following.scale_to, following.crop_x)


def test_without_a_reel_every_clip_uses_the_single_source():
    assert {c.src for c in build().video} == {"take.mp4"}
