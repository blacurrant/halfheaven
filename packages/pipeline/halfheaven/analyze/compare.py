"""How close did we get?

This project's only real success criterion is a visual similarity judgement,
and until now nothing anywhere scored it. That absence is what let a caption
track drift 1.4 seconds and a grade turn magenta across five commits: with no
number to watch, "progress" quietly became "another feature landed, tests
green".

Scoring is a diff of two fingerprints. The output is measured exactly the way
the reference was, and each trait is compared on its own terms - a shot length
by ratio, an on-beat share by difference, a colour by perceptual distance -
because a single euclidean number over mixed units would be meaningless and
worse, would look authoritative.

Each trait carries a tolerance: the band inside which two reels read as having
made the same choice. Those are judgements, not physics, and they are written
here in one place so they can be argued with rather than buried in a formula.

A trait neither side could measure is *not* scored. Counting it as a match
would flatter us for a reading we never took, and counting it as a miss would
punish us for a reference that simply has no captions.
"""
from __future__ import annotations

import dataclasses
import enum
import pathlib
from dataclasses import dataclass
from typing import Any, Callable

from halfheaven.analyze.fingerprint import (
    Confidence,
    Fingerprint,
    Reading,
    extract_fingerprint,
)


class Verdict(enum.Enum):
    MATCH = "match"
    NEAR = "near"
    MISS = "miss"
    UNSCORED = "unscored"


@dataclass(frozen=True)
class Trait:
    """One comparable property, and what counts as close enough."""

    group: str
    field: str
    label: str
    # distance(ours, theirs) in the trait's own units
    distance: Callable[[Any, Any], float]
    tolerance: float          # at or under this, the same choice
    near: float               # at or under this, recognisably similar
    unit: str = ""


def _abs(a: Any, b: Any) -> float:
    return abs(float(a) - float(b))


def _ratio(a: Any, b: Any) -> float:
    """Symmetric relative difference: 0 when equal, 1 when one is double."""
    a, b = float(a), float(b)
    if a <= 0 or b <= 0:
        return 1.0
    return abs(a - b) / max(a, b)


def _same(a: Any, b: Any) -> float:
    return 0.0 if a == b else 1.0


def _hex_to_lab(value: str) -> tuple[float, float, float]:
    import cv2
    import numpy as np

    value = value.lstrip("#")
    rgb = np.array([[[int(value[i:i + 2], 16) for i in (0, 2, 4)]]], np.uint8)
    lab = cv2.cvtColor(rgb[:, :, ::-1], cv2.COLOR_BGR2LAB)[0, 0].astype(float)
    return lab[0] * 100 / 255, lab[1] - 128, lab[2] - 128


def _delta_e(a: Any, b: Any) -> float:
    """Plain CIE76. Good enough to say "that is not the same colour"."""
    la, aa, ba = _hex_to_lab(str(a))
    lb, ab, bb = _hex_to_lab(str(b))
    return ((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2) ** 0.5


def _lab_distance(a: Any, b: Any) -> float:
    return sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)) ** 0.5


# The traits worth scoring, and how forgiving to be about each. A shot length
# within 25% reads as the same pace; a caption sitting a tenth of a frame
# lower does not read as a different design. These numbers are the argument.
TRAITS: tuple[Trait, ...] = (
    Trait("rhythm", "median_shot", "shot length", _ratio, 0.25, 0.45),
    Trait("rhythm", "cuts_per_min", "cut density", _ratio, 0.25, 0.45),
    Trait("rhythm", "on_beat_share", "cuts on the beat", _abs, 0.15, 0.30),
    Trait("rhythm", "driver", "what drives the cut", _same, 0.0, 0.0),
    Trait("structure", "card_share", "share that isn't footage", _abs, 0.08, 0.18),
    Trait("structure", "static_share", "camera stillness", _abs, 0.15, 0.30),
    Trait("structure", "push_share", "push-ins", _abs, 0.06, 0.15),
    Trait("structure", "plate_hex", "card colour", _delta_e, 12.0, 30.0, "ΔE"),
    Trait("text", "duty_cycle", "time carrying type", _abs, 0.10, 0.22),
    Trait("text", "size_pct", "type size", _ratio, 0.30, 0.55),
    Trait("text", "spread", "how much type moves", _abs, 0.05, 0.11),
    Trait("text", "placement", "type placement", _same, 0.0, 0.0),
    Trait("text", "accent_rate", "how often an accent appears", _abs, 0.15, 0.30),
    Trait("text", "accent_hex", "accent colour", _delta_e, 12.0, 30.0, "ΔE"),
    Trait("text", "all_caps", "capitalisation", _same, 0.0, 0.0),
    Trait("text", "italic", "italic", _same, 0.0, 0.0),
    Trait("text", "contrast", "stroke contrast", _abs, 0.08, 0.18),
    Trait("text", "weight", "weight", _ratio, 0.20, 0.35),
    Trait("text", "typeface", "typeface", _same, 0.0, 0.0),
    Trait("text", "decor", "outline or shadow", _same, 0.0, 0.0),
    Trait("grade", "lab_mean", "colour", _lab_distance, 6.0, 14.0, "ΔLAB"),
)


@dataclass
class Scored:
    trait: Trait
    verdict: Verdict
    ours: Any = None
    theirs: Any = None
    distance: float | None = None
    why: str = ""


@dataclass
class Scorecard:
    output: str
    reference: str
    rows: list[Scored]

    @property
    def scored(self) -> list[Scored]:
        return [row for row in self.rows if row.verdict is not Verdict.UNSCORED]

    @property
    def matches(self) -> int:
        return sum(1 for row in self.scored if row.verdict is Verdict.MATCH)

    @property
    def nears(self) -> int:
        return sum(1 for row in self.scored if row.verdict is Verdict.NEAR)

    @property
    def score(self) -> float:
        """Share of comparable traits we got right, counting near as half.

        Deliberately not a percentage of everything: the denominator is what
        could actually be compared, and `unscored` is reported beside it so a
        high score on three traits cannot masquerade as a high score.
        """
        if not self.scored:
            return 0.0
        return (self.matches + 0.5 * self.nears) / len(self.scored)


def _reading(fingerprint: Fingerprint, group: str, field: str) -> Reading | None:
    section = getattr(fingerprint, group, None)
    if section is None:
        return None
    return getattr(section, field, None)


def compare(ours: Fingerprint, theirs: Fingerprint) -> Scorecard:
    """Score one fingerprint against another, trait by trait."""
    rows: list[Scored] = []
    for trait in TRAITS:
        mine = _reading(ours, trait.group, trait.field)
        yours = _reading(theirs, trait.group, trait.field)

        if mine is None or yours is None:
            rows.append(Scored(trait, Verdict.UNSCORED, why="not measured by this version"))
            continue
        missing = [
            name for name, reading in (("output", mine), ("reference", yours))
            if reading.confidence is Confidence.ABSENT or reading.value is None
        ]
        if missing:
            rows.append(Scored(
                trait, Verdict.UNSCORED,
                ours=mine.value, theirs=yours.value,
                why=f"no reading from the {' or the '.join(missing)}",
            ))
            continue

        try:
            gap = trait.distance(mine.value, yours.value)
        except (TypeError, ValueError):
            rows.append(Scored(trait, Verdict.UNSCORED, why="values are not comparable"))
            continue

        verdict = (
            Verdict.MATCH if gap <= trait.tolerance
            else Verdict.NEAR if gap <= trait.near
            else Verdict.MISS
        )
        rows.append(Scored(trait, verdict, mine.value, yours.value, gap))

    return Scorecard(output=ours.source, reference=theirs.source, rows=rows)


_SIGN = {Verdict.MATCH: "✓", Verdict.NEAR: "≈", Verdict.MISS: "✗", Verdict.UNSCORED: "·"}


def render(card: Scorecard) -> str:
    def show(value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, (list, tuple)):
            return ", ".join(f"{v:.1f}" if isinstance(v, float) else str(v) for v in value)
        if isinstance(value, float):
            return f"{value:.3f}"
        return str(value)

    lines = [
        f"output    {card.output}",
        f"reference {card.reference}",
        "",
        f"{'':2} {'trait':<28} {'output':<16} {'reference':<16} gap",
    ]
    group = None
    for row in card.rows:
        if row.trait.group != group:
            group = row.trait.group
            lines.append(f"\n[{group}]")
        gap = "" if row.distance is None else f"{row.distance:.3f}{row.trait.unit and ' ' + row.trait.unit}"
        note = f"   {row.why}" if row.verdict is Verdict.UNSCORED and row.why else ""
        lines.append(
            f"{_SIGN[row.verdict]:2} {row.trait.label:<28} "
            f"{show(row.ours):<16} {show(row.theirs):<16} {gap}{note}"
        )

    unscored = len(card.rows) - len(card.scored)
    lines += [
        "",
        f"{card.matches} matched, {card.nears} close, "
        f"{len(card.scored) - card.matches - card.nears} missed, {unscored} not comparable",
        f"score {card.score:.0%} of the {len(card.scored)} traits that could be compared",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Score an edited output against the reference it was meant to resemble.")
    parser.add_argument("output", help="what the pipeline produced")
    parser.add_argument("reference", help="the reel it was copying")
    parser.add_argument("--stride", type=int, default=3,
                        help="sample every nth frame (default 3)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    ours = extract_fingerprint(args.output, stride=args.stride)
    theirs = extract_fingerprint(args.reference, stride=args.stride)
    card = compare(ours, theirs)

    if args.json:
        import json

        print(json.dumps({
            "output": card.output,
            "reference": card.reference,
            "score": round(card.score, 4),
            "rows": [
                {"group": r.trait.group, "field": r.trait.field, "label": r.trait.label,
                 "verdict": r.verdict.value, "ours": r.ours, "theirs": r.theirs,
                 "gap": r.distance, "why": r.why}
                for r in card.rows
            ],
        }, indent=2, default=str))
    else:
        print(render(card))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
