"""The recut entry point: edits in, rendered file out, pipeline untouched."""
import json
import pathlib

import pytest

from halfheaven.recut import main, parse_edits
from halfheaven.media.probe import probe
from halfheaven.schemas import Canvas, Caption, CaptionProfile, EditProgram, TextRun, VideoClip

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SOURCE = FIXTURES / "three_shots_at_1.0_3.0.mp4"


def written_program(tmp_path):
    prog = EditProgram(
        canvas=Canvas(width=320, height=568, fps=30),
        video=[VideoClip(src=str(SOURCE), start=0.0, end=2.0)],
        captions=[Caption(t=0.0, duration=1.4, runs=[
            TextRun(text="I", t=0.0), TextRun(text="phone", t=0.7)])],
        styles={"default": CaptionProfile(present=True, size_pct=0.07, enter="none")},
    )
    path = tmp_path / "edit_program.json"
    path.write_text(prog.model_dump_json(indent=2))
    return path


def test_unknown_keys_in_an_edit_are_dropped():
    edits = parse_edits('[{"index":0,"text":"hi","bogus":1}]')
    assert len(edits) == 1 and edits[0].text == "hi"


def test_an_edit_without_an_index_is_skipped():
    assert parse_edits('[{"text":"hi"}]') == []


def test_a_recut_writes_a_playable_file(tmp_path):
    path = written_program(tmp_path)
    out = tmp_path / "out.mp4"
    assert main(["--program", str(path), "--out", str(out),
                 "--work", str(tmp_path / "w"), "--edits", "[]"]) == 0
    assert probe(out).duration == pytest.approx(2.0, abs=0.2)


def test_a_correction_is_saved_back_into_the_program(tmp_path):
    path = written_program(tmp_path)
    main(["--program", str(path), "--out", str(tmp_path / "o.mp4"),
          "--work", str(tmp_path / "w"),
          "--edits", json.dumps([{"index": 0, "text": "iPhone"}])])
    saved = json.loads(path.read_text())
    assert [r["text"] for r in saved["captions"][0]["runs"]] == ["iPhone"]


def test_deleting_the_only_card_still_renders(tmp_path):
    path = written_program(tmp_path)
    out = tmp_path / "out.mp4"
    main(["--program", str(path), "--out", str(out), "--work", str(tmp_path / "w"),
          "--edits", json.dumps([{"index": 0, "delete": True}])])
    assert probe(out).duration == pytest.approx(2.0, abs=0.2)
