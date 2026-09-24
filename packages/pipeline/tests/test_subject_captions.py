"""Captions that know where the speaker is: around them, or behind them."""
import pathlib
import tempfile

import numpy as np

from halfheaven.analyze.segment import write_matte_video
from halfheaven.plan.subject_captions import (
    CLEAR, MAX_COVER, MIN_COVER, _cover, _ink, _matte_at, place_around_subject, send_behind,
)
from halfheaven.schemas import Canvas, Caption, CaptionProfile, EditProgram, TextRun, VideoClip

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
BARS = FIXTURES / "three_shots_at_1.0_3.0.mp4"      # 320x568, 4.5s
CANVAS = Canvas(width=320, height=568, fps=30)
HEAD_TOP = 0.35


class Speaker:
    """A head-and-shoulders block: its top at HEAD_TOP, a third of the frame wide."""

    def mask_for(self, frame):
        height, width = frame.shape[:2]
        mask = np.zeros((height, width), np.uint8)
        mask[int(HEAD_TOP * height):, int(0.33 * width): int(0.67 * width)] = 255
        return mask


class Nobody:
    def mask_for(self, frame):
        return np.zeros(frame.shape[:2], np.uint8)


class Everywhere:
    def mask_for(self, frame):
        return np.full(frame.shape[:2], 255, np.uint8)


def stressed(t, word="BIG"):
    return Caption(t=t, duration=0.7, runs=[TextRun(text=word, style="emphasis", t=t),
                                            TextRun(text="IDEA", t=t + 0.2)])


def program(captions):
    return EditProgram(
        canvas=CANVAS, video=[VideoClip(src=str(BARS), start=0.0, end=4.5)], captions=captions,
        styles={"default": CaptionProfile(present=True, size_pct=0.06),
                "emphasis": CaptionProfile(present=True, size_pct=0.09)},
    )


def test_a_stressed_card_is_tucked_behind_the_head(tmp_path):
    track = write_matte_video(BARS, Speaker(), tmp_path / "s.mp4", feather=0)
    result = send_behind(program([stressed(0.3)]), track)
    card = result.captions[0]
    assert card.behind
    assert abs(card.anchor[1] - HEAD_TOP) < 0.08, "sits at the top of the head"
    assert abs(card.anchor[0] - 0.5) < 0.05, "centred on the head"
    with tempfile.TemporaryDirectory() as scratch:
        ink = _ink(card, result, card.anchor, pathlib.Path(scratch))
    cover = _cover(ink, _matte_at(track, 0.65, result))
    assert MIN_COVER <= cover <= MAX_COVER, "visibly behind, still readable"


def test_only_stressed_cards_go_behind_and_not_back_to_back(tmp_path):
    track = write_matte_video(BARS, Speaker(), tmp_path / "s.mp4", feather=0)
    plain = Caption(t=1.2, duration=0.6, text="just words")
    cards = send_behind(program([stressed(0.2), plain, stressed(2.0), stressed(3.2)]),
                        track, min_gap=2.5).captions
    assert [c.behind for c in cards] == [True, False, False, True]
    assert cards[1].anchor == plain.anchor, "a card left in front keeps its place"


def test_no_subject_means_nothing_goes_behind(tmp_path):
    track = write_matte_video(BARS, Nobody(), tmp_path / "s.mp4", feather=0)
    assert not any(c.behind for c in send_behind(program([stressed(0.3)]), track).captions)


def test_a_card_the_subject_would_mostly_hide_stays_in_front(tmp_path):
    track = write_matte_video(BARS, Everywhere(), tmp_path / "s.mp4", feather=0)
    assert not any(c.behind for c in send_behind(program([stressed(0.3)]), track).captions)


# --- around ---------------------------------------------------------------------


def plain(t, anchor):
    return Caption(t=t, duration=0.7, text="words on the body", anchor=anchor)


def test_a_card_on_the_speaker_moves_off_them(tmp_path):
    track = write_matte_video(BARS, Speaker(), tmp_path / "s.mp4", feather=0)
    result = place_around_subject(program([plain(0.3, (0.5, 0.6))]), "around", track)
    card = result.captions[0]
    assert card.home == (0.5, 0.6) and card.anchor != (0.5, 0.6)
    with tempfile.TemporaryDirectory() as scratch:
        ink = _ink(card, result, card.anchor, pathlib.Path(scratch))
    assert _cover(ink, _matte_at(track, 0.65, result)) <= CLEAR
    assert not card.behind


def test_a_card_already_clear_of_the_speaker_stays_put(tmp_path):
    track = write_matte_video(BARS, Speaker(), tmp_path / "s.mp4", feather=0)
    card = place_around_subject(program([plain(0.3, (0.5, 0.15))]), "around", track).captions[0]
    assert card.anchor == (0.5, 0.15) and card.home is None


def test_switching_modes_starts_from_the_original_placement(tmp_path):
    track = write_matte_video(BARS, Speaker(), tmp_path / "s.mp4", feather=0)
    original = program([stressed(0.3), plain(1.5, (0.5, 0.6))])
    homes = [c.anchor for c in original.captions]

    behind = place_around_subject(original, "behind", track)
    around = place_around_subject(behind, "around", track)
    assert not any(c.behind for c in around.captions), "no card stays behind in another mode"
    assert [c.home or c.anchor for c in around.captions] == homes

    off = place_around_subject(around, "off", track)
    assert [c.anchor for c in off.captions] == homes
    assert all(c.home is None and not c.behind for c in off.captions)
