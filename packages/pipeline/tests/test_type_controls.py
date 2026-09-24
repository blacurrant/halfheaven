"""A creator's own caption type: colours, size, face and edge, for normal and pop words."""
import numpy as np
import pytest
from PIL import Image

from halfheaven.recut import apply_type
from halfheaven.render.captions import render_caption
from halfheaven.render.fonts import available, catalogue
from halfheaven.schemas import Canvas, CaptionProfile, EditProgram, StyleProfile, TextRun, VideoClip

CANVAS = Canvas(width=320, height=568, fps=30)


def program():
    return EditProgram(canvas=CANVAS, video=[VideoClip(src="x.mp4", start=0, end=1)],
                       styles={"default": CaptionProfile(present=True),
                               "emphasis": CaptionProfile(present=True, fill_hex="#FFFFFF")})


def test_both_kinds_of_word_take_their_own_settings():
    face = available()[3].file
    profile, result = apply_type(StyleProfile(), program(), {
        "body": {"fill_hex": "#00FF00", "size_pct": 0.05, "font_file": face, "all_caps": True},
        "pop": {"fill_hex": "#FF3366", "decor": "shadow_soft", "shadow_hex": "#112233"},
    })
    body, pop = result.styles["default"], result.styles["emphasis"]
    assert (body.fill_hex, body.size_pct, body.font_file, body.all_caps) == ("#00FF00", 0.05, face, True)
    assert (pop.fill_hex, pop.decor, pop.shadow_hex) == ("#FF3366", "shadow_soft", "#112233")
    assert profile.captions == body and profile.emphasis == pop, "kept for the next re-render"


def test_a_setting_left_out_is_left_alone():
    _, result = apply_type(StyleProfile(), program(), {"pop": {"fill_hex": "#FF0000"}})
    assert result.styles["default"] == program().styles["default"]


@pytest.mark.parametrize("patch", [
    {"body": {"fill_hex": "red; rm"}},
    {"body": {"size_pct": 0.9}},
    {"body": {"font_file": "../../etc/passwd"}},
    {"body": {"font_weight": 50}},
    {"body": {"reveal": "karaoke"}},
    {"title": {"fill_hex": "#FFFFFF"}},
    {"body": {"decor": "sparkles"}},
])
def test_anything_else_is_refused(patch):
    with pytest.raises(ValueError):
        apply_type(StyleProfile(), program(), patch)


def test_the_chosen_colour_is_what_gets_drawn(tmp_path):
    _, result = apply_type(StyleProfile(), program(),
                           {"pop": {"fill_hex": "#FF0000", "decor": "none", "size_pct": 0.1}})
    card = render_caption([TextRun(text="POP", style="emphasis")], CANVAS, result.styles,
                          tmp_path / "c.png")
    pixels = np.array(Image.open(card).convert("RGBA")).reshape(-1, 4)
    ink = pixels[pixels[:, 3] > 250][:, :3]
    assert len(ink) and np.abs(ink.mean(axis=0) - (255, 0, 0)).max() < 10


def test_the_catalogue_says_which_faces_take_a_weight():
    faces = {f["file"]: f for f in catalogue()}
    assert len(faces) == len(available())
    assert any(f["weights"] for f in faces.values()) and any(not f["weights"] for f in faces.values())
    for face in faces.values():
        if face["weights"]:
            low, high = face["weights"]
            assert 100 <= low < high <= 1000
