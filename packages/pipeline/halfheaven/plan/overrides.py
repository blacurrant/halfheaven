"""Applying a creator's adjustments on top of a measured profile.

The reference gives a starting point, not a verdict. "Bigger captions" or "cut
it tighter" arrives here as a small patch over the measured StyleProfile, so
what we measured and what they asked for stay separable - either can be shown
on its own, and undoing a wish never disturbs the measurement.

Patches originate from a language model reading a sentence, so anything
unrecognised or out of range is dropped rather than forced through. A wish we
could not honour leaves the edit as it was; a wish we mangle produces a broken
video the creator cannot explain.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from halfheaven.schemas import StyleProfile


def _patch_section(section: BaseModel, patch: dict[str, Any]) -> BaseModel:
    updated = section
    for field, value in patch.items():
        if field not in type(section).model_fields:
            continue  # not a knob we expose
        try:
            candidate = updated.model_copy(update={field: value})
            type(section).model_validate(candidate.model_dump())
        except ValidationError:
            continue  # out of range: the model misread, so leave it alone
        updated = candidate
    return updated


def apply_overrides(profile: StyleProfile, overrides: dict[str, Any]) -> StyleProfile:
    """A copy of `profile` with `overrides` merged in, section by section."""
    if not overrides:
        return profile

    changes: dict[str, Any] = {}
    for name, patch in overrides.items():
        if name not in StyleProfile.model_fields or not isinstance(patch, dict):
            continue
        section = getattr(profile, name)
        if not isinstance(section, BaseModel):
            continue
        changes[name] = _patch_section(section, patch)

    return profile.model_copy(update=changes) if changes else profile
