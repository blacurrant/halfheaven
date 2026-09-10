"""Role-based font resolution.

The reference uses two type systems: monospace for running dialogue and a
high-contrast serif for single-word emphasis. We cannot identify a specific
typeface from pixels reliably, so the vision pass classifies a *category* and
this module maps that category to a font we are entitled to embed.
"""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from halfheaven.render.fonts import CATEGORIES, load_font, resolve_font_path


def test_every_declared_category_resolves_to_a_real_file():
    # a category that resolves to nothing would fail at render time on a worker
    for category in CATEGORIES:
        assert resolve_font_path(category).exists(), f"{category} has no usable font"


def test_an_unknown_category_falls_back_rather_than_raising():
    assert resolve_font_path("no-such-category").exists()


def test_resolution_is_deterministic():
    assert resolve_font_path("didone") == resolve_font_path("didone")


def test_a_loaded_font_has_the_requested_size():
    assert load_font("mono", 48).size == 48


def test_categories_actually_differ_from_one_another():
    # if two categories silently resolved to the same fallback, emphasis would
    # look identical to body text and the effect would be invisible
    rendered = {}
    for category in ("mono", "didone", "grotesque"):
        image = Image.new("L", (400, 120), 0)
        ImageDraw.Draw(image).text((10, 10), "SALT", font=load_font(category, 72), fill=255)
        rendered[category] = np.array(image)
    assert not np.array_equal(rendered["mono"], rendered["didone"])
    assert not np.array_equal(rendered["grotesque"], rendered["didone"])


def advance(category, glyph):
    return load_font(category, 96).getlength(glyph)


def test_the_mono_category_really_is_monospaced():
    # the defining property: every glyph advances the same width
    assert advance("mono", "i") == pytest.approx(advance("mono", "W"))


def test_the_proportional_categories_are_not_monospaced():
    for category in ("didone", "grotesque"):
        assert advance(category, "i") != pytest.approx(advance(category, "W")), category


def test_the_emphasis_and_body_categories_are_different_files():
    # if these collapsed to one fallback, emphasis would be invisible
    assert resolve_font_path("didone") != resolve_font_path("mono")


# --- bundled, not borrowed ----------------------------------------------------
# The first registry pointed at macOS system fonts. Those cannot ship: they are
# not ours to embed, and a Linux worker does not have them. Every face is now a
# file in the repo under a licence that permits embedding.


def test_every_category_resolves_inside_the_repo():
    from halfheaven.render.fonts import ASSET_DIR

    for category in CATEGORIES:
        path = resolve_font_path(category)
        assert ASSET_DIR in path.parents, f"{category} resolves outside the bundle: {path}"


def test_the_bundle_carries_its_licences():
    from halfheaven.render.fonts import ASSET_DIR

    licences = list(ASSET_DIR.glob("*OFL*")) + list(ASSET_DIR.glob("*LICEN*"))
    assert licences, "fonts shipped without their licence text"


def test_a_variable_face_can_be_set_heavy():
    # Montserrat ships as one variable file whose default weight is 400, which
    # reads as weak at caption size; captions want 700-900.
    light = load_font("grotesque", 96, 400).getlength("HELLO")
    heavy = load_font("grotesque", 96, 900).getlength("HELLO")
    assert heavy > light, "weight axis had no effect"


def test_asking_for_a_weight_a_face_lacks_still_returns_a_font():
    assert load_font("display", 48, 900).size == 48   # Anton is single-weight
