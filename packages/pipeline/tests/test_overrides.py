"""Applying user adjustments on top of a measured profile.

The reference gives us a starting point, not a verdict. When a creator says
"bigger captions" or "cut it tighter", that arrives here as a small patch over
the measured StyleProfile - so their wish and our measurement stay separable
and either can be inspected on its own.
"""
import pytest

from halfheaven.plan.overrides import apply_overrides
from halfheaven.schemas import StyleProfile


def test_no_overrides_leaves_the_profile_untouched():
    base = StyleProfile()
    assert apply_overrides(base, {}) == base


def test_a_nested_value_is_replaced():
    out = apply_overrides(StyleProfile(), {"captions": {"size_pct": 0.09}})
    assert out.captions.size_pct == pytest.approx(0.09)


def test_untouched_siblings_survive_a_nested_patch():
    base = StyleProfile()
    base = base.model_copy(update={"captions": base.captions.model_copy(update={"fill_hex": "#ABCDEF"})})
    out = apply_overrides(base, {"captions": {"size_pct": 0.09}})
    assert out.captions.fill_hex == "#ABCDEF"


def test_several_sections_can_be_patched_at_once():
    out = apply_overrides(StyleProfile(), {
        "captions": {"size_pct": 0.08},
        "trim": {"aggressiveness": 0.9},
        "grade": {"strength": 0.2},
    })
    assert out.captions.size_pct == pytest.approx(0.08)
    assert out.trim.aggressiveness == pytest.approx(0.9)
    assert out.grade.strength == pytest.approx(0.2)


def test_an_unknown_section_is_ignored_rather_than_fatal():
    # the adjustment comes from a language model reading a creator's sentence
    out = apply_overrides(StyleProfile(), {"nonsense": {"x": 1}})
    assert out == StyleProfile()


def test_an_unknown_field_within_a_real_section_is_ignored():
    out = apply_overrides(StyleProfile(), {"captions": {"not_a_field": 3}})
    assert out.captions == StyleProfile().captions


def test_a_value_outside_the_allowed_range_is_rejected_not_clamped():
    # aggressiveness is 0..1; a model returning 5 means it misread, and
    # silently clamping would hide that
    out = apply_overrides(StyleProfile(), {"trim": {"aggressiveness": 5}})
    assert out.trim.aggressiveness == StyleProfile().trim.aggressiveness


def test_a_valid_patch_still_applies_when_a_sibling_is_invalid():
    out = apply_overrides(StyleProfile(), {"trim": {"aggressiveness": 5, "max_silence": 0.4}})
    assert out.trim.max_silence == pytest.approx(0.4)
