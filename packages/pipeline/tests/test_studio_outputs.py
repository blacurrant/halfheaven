"""What the pipeline leaves on disk for the studio: the words it heard, what it
cut, the look it was first made with, and stills of every other look."""
import json
import pathlib

from PIL import Image

from halfheaven.cli import write_decided, write_heard
from halfheaven.groq.asr import Transcript
from halfheaven.models import Word
from halfheaven.plan.builder import Decisions
from halfheaven.previews import frame_at, moment, render_previews
from halfheaven.recut import main as recut
from halfheaven.render.presets import CAPTION_PRESETS
from halfheaven.schemas import (Canvas, Caption, CaptionProfile, EditProgram, StyleProfile,
                                TextRun, VideoClip)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SOURCE = FIXTURES / "three_shots_at_1.0_3.0.mp4"


def test_the_words_heard_are_written_with_their_times(tmp_path):
    words = [Word("so", 0.0, 0.2), Word("um", 0.25, 0.4), Word("hello", 0.5, 0.9)]
    write_heard(tmp_path, Transcript(words=words, duration=1.0, text="so um hello"))
    heard = json.loads((tmp_path / "transcript.json").read_text())
    assert [w["text"] for w in heard["words"]] == ["so", "um", "hello"]
    assert heard["words"][1] == {"text": "um", "start": 0.25, "end": 0.4}


def test_cuts_are_written_as_half_open_word_ranges(tmp_path):
    decisions = Decisions(cuts=[(1, 2)], caption_chunks=[], punch_word_indices=[2],
                          emphasis_word_indices=[2])
    write_decided(tmp_path, decisions)
    decided = json.loads((tmp_path / "decisions.json").read_text())
    assert decided == {"cuts": [[1, 2]], "emphasis": [2], "punch": [2]}


def program_on_disk(tmp_path, styles=None):
    program = EditProgram(
        canvas=Canvas(width=320, height=568, fps=30),
        video=[VideoClip(src=str(SOURCE), start=0.0, end=2.0)],
        captions=[Caption(t=0.0, duration=1.8, runs=[
            TextRun(text="I", t=0.0), TextRun(text="still", t=0.5),
            TextRun(text="ride", t=1.0, style="emphasis")])],
        styles=styles or {"default": CaptionProfile(present=True, size_pct=0.07, enter="none"),
                          "emphasis": CaptionProfile(present=True, size_pct=0.09, enter="none")},
    )
    path = tmp_path / "edit_program.json"
    path.write_text(program.model_dump_json(indent=2))
    return path, program


def test_the_matched_look_restores_the_captions_first_measured(tmp_path):
    path, _ = program_on_disk(tmp_path)
    first = StyleProfile(captions=CaptionProfile(present=True, size_pct=0.07, fill_hex="#C9DFF7"))
    (tmp_path / "style_profile.json").write_text(first.model_dump_json())
    (tmp_path / "style_profile.matched.json").write_text(first.model_dump_json())
    work = tmp_path / "w"

    recut(["--program", str(path), "--out", str(tmp_path / "a.mp4"), "--work", str(work),
           "--preset", "beast"])
    assert json.loads(path.read_text())["styles"]["default"]["size_pct"] != 0.07

    recut(["--program", str(path), "--out", str(tmp_path / "b.mp4"), "--work", str(work),
           "--preset", "matched"])
    styles = json.loads(path.read_text())["styles"]
    assert styles["default"]["size_pct"] == 0.07
    assert styles["default"]["fill_hex"] == "#C9DFF7"


def test_the_moment_shown_is_inside_a_card(tmp_path):
    _, program = program_on_disk(tmp_path)
    at = moment(program)
    card, frame = frame_at(program, at)
    assert card.t <= at <= card.t + card.duration
    assert frame.runs


def test_every_look_gets_a_still_of_the_real_render(tmp_path):
    path, _ = program_on_disk(tmp_path)
    made = render_previews(path, tmp_path, tmp_path / "previews", base=SOURCE, width=90)
    assert [m["id"] for m in made] == list(CAPTION_PRESETS)
    for entry in made:
        still = Image.open(tmp_path / "previews" / entry["file"])
        assert still.size == (90, 160)
    # the looks draw differently, so the stills must not all be the same picture
    pixels = {Image.open(tmp_path / "previews" / m["file"]).tobytes() for m in made}
    assert len(pixels) > 1


def test_the_matched_still_comes_first_when_the_first_look_was_kept(tmp_path):
    path, _ = program_on_disk(tmp_path)
    (tmp_path / "style_profile.matched.json").write_text(StyleProfile().model_dump_json())
    made = render_previews(path, tmp_path, tmp_path / "previews", base=SOURCE, width=90)
    assert made[0]["id"] == "matched"
