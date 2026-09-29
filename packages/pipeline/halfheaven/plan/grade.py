"""Choosing and baking the grade for a set of takes.

Two grades exist. The colourist grade (plan/colourist.py) needs the
reference's zones and a subject and skin matte for every take. The single
statistical LUT is what runs when it cannot be made, and it is always baked,
so a render that loses a matte still has a grade to fall back to.
"""
from __future__ import annotations

import pathlib

from halfheaven.analyze.framing import detect_letterbox
from halfheaven.analyze.grade import measure_color_stats
from halfheaven.analyze.zones import take_zone_look
from halfheaven.plan.colourist import plan_grade
from halfheaven.render.lut import ColorStats, write_lut, write_zone_luts
from halfheaven.schemas import GradeControls, StyleProfile, TakeMatte, ZoneGrade


def global_lut_for(profile: StyleProfile, takes: list[str],
                   work: str | pathlib.Path) -> tuple[pathlib.Path, ColorStats] | None:
    """The single LUT, from the first take's colour to the reference's, and the take's stats.

    Measured from the first take: several takes of one setup share a look.
    Strength is a dial because pushing bright footage all the way to a dark
    reference turns it muddy.
    """
    if not profile.grade.measured:
        return None
    primary = takes[0]
    source = measure_color_stats(primary, framing=detect_letterbox(primary))
    lut = write_lut(source=source,
                    target=ColorStats(mean=profile.grade.lab_mean, std=profile.grade.lab_std),
                    out_path=pathlib.Path(work) / "grade.cube", strength=profile.grade.strength)
    return lut, source


def zone_grade_for(profile: StyleProfile, takes: list[str], mattes: dict[str, TakeMatte],
                   work: str | pathlib.Path) -> ZoneGrade | None:
    """The colourist grade for these takes, or None when it cannot be made.

    None when the reference showed no readable person, or when any take lacks
    a subject or skin matte. The caller then keeps the single LUT.
    """
    reference = profile.grade.zones
    if reference is None or any(take not in mattes or not mattes[take].skin for take in takes):
        return None
    take = take_zone_look(takes, mattes)
    if take is None:
        return None
    controls = plan_grade(take, reference, profile.grade.strength)
    luts = write_zone_luts(controls, pathlib.Path(work) / "grade")
    return ZoneGrade(subject_lut=str(luts["subject"]), background_lut=str(luts["background"]),
                     skin_lut=str(luts["skin"]), controls=controls)


def describe_controls(controls: GradeControls) -> str:
    return (f"white balance {controls.white_balance_deg:+.1f}°, "
            f"exposure anchor x{controls.exposure_anchor:.2f}, "
            f"saturation subject x{controls.subject.saturation:.2f} "
            f"background x{controls.background.saturation:.2f}, "
            f"skin richness x{controls.skin_chroma:.2f}, face {controls.face_lift:+.1f} L, "
            f"strength {controls.strength:.2f}")
