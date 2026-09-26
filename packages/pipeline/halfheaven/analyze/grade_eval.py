"""Does the colourist grade beat today's, and does it hold together at the edge?

Runs the grade alone - no transcription, no editing - on whole takes. Each take
is rendered once with today's single LUT and once with the colourist grade,
through the real renderer, and both are measured against the reference.

    python -m halfheaven.analyze.grade_eval --takes a.mp4 b.mp4 \\
        --references r1.mp4 r2.mp4 --out work/grade_eval [--strength 0.85]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

import cv2
import numpy as np

from halfheaven.analyze.fingerprint import extract_fingerprint
from halfheaven.analyze.matte import matte_takes
from halfheaven.analyze.zones import shrink, summarise, take_zone_look, to_lab
from halfheaven.media.probe import probe
from halfheaven.plan.grade import global_lut_for, zone_grade_for
from halfheaven.plan.typography import apply_fingerprint
from halfheaven.render.video import extract_frame, render
from halfheaven.schemas import Canvas, EditProgram, Look, StyleProfile, TakeMatte, VideoClip

SEAM_LIMIT = 2.0        # L: a rim or line the grade may add at the matte edge
FLICKER_LIMIT = 1.0     # L per frame the grade may add over the room or the face
FACE_LIMIT = 2.0        # L the face may move from the raw footage
# Rings round the matte's 0.5 contour, as shares of frame height.
EDGE_RING = 0.0035
NEAR_RING = (0.005, 0.014)
MIN_RING_PIXELS = 50


def _signed_distance(alpha: np.ndarray) -> np.ndarray:
    """Pixels from the matte's 0.5 contour: positive inside the subject, negative outside."""
    inside = (alpha > 0.5).astype(np.uint8)
    depth = cv2.distanceTransform(inside, cv2.DIST_L2, 3)
    reach = cv2.distanceTransform(1 - inside, cv2.DIST_L2, 3)
    return np.where(inside > 0, depth, -reach)


def seam(lightness: np.ndarray, alpha: np.ndarray) -> float | None:
    """How much brighter (+) or darker (-) the matte's edge is than both sides of it, in L.

    A rim or an outline is exactly an extreme at the edge. Compare an output's
    seam with the raw footage's: hair has its own dark edge before any grade.
    """
    distance = _signed_distance(alpha) / alpha.shape[0]
    edge = np.abs(distance) <= EDGE_RING
    inner = (distance >= NEAR_RING[0]) & (distance <= NEAR_RING[1])
    outer = (distance <= -NEAR_RING[0]) & (distance >= -NEAR_RING[1])
    if min(edge.sum(), inner.sum(), outer.sum()) < MIN_RING_PIXELS:
        return None
    return float(lightness[edge].mean() - (lightness[inner].mean() + lightness[outer].mean()) / 2)


def flicker(frames: list[np.ndarray], raw_frames: list[np.ndarray], alphas: list[np.ndarray],
            skins: list[np.ndarray]) -> dict[str, float | None]:
    """Frame-to-frame change in L the grade adds over the footage's own, for the room and the face."""
    room, face = [], []
    for k in range(1, len(frames)):
        raw_change = np.abs(raw_frames[k] - raw_frames[k - 1])
        still = (alphas[k] < 0.1) & (alphas[k - 1] < 0.1) & (raw_change < 1.0)
        if still.sum() >= 500:
            room.append(float(np.abs(frames[k] - frames[k - 1])[still].mean() - raw_change[still].mean()))
        now, before = skins[k] > 0.6, skins[k - 1] > 0.6
        if now.sum() >= 200 and before.sum() >= 200:
            graded = abs(np.median(frames[k][now]) - np.median(frames[k - 1][before]))
            shot = abs(np.median(raw_frames[k][now]) - np.median(raw_frames[k - 1][before]))
            face.append(float(graded - shot))
    return {"room": float(np.mean(room)) if room else None,
            "face": float(np.mean(face)) if face else None}


ZONE_TRAITS = ("face_above_background", "background_l", "skin_chroma", "skin_hue", "shadow_tint")
SEAM_FRAMES = 8
FLICKER_STARTS = (0.2, 0.5, 0.8)
FLICKER_RUN = 8


def _frame_count(path: str | pathlib.Path) -> int:
    capture = cv2.VideoCapture(str(path))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    return count


def _read(path: str | pathlib.Path, indices: list[int]) -> list[np.ndarray | None]:
    capture = cv2.VideoCapture(str(path))
    frames: list[np.ndarray | None] = []
    try:
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            frames.append(frame if ok else None)
    finally:
        capture.release()
    return frames


def _lightness(path, indices) -> list[np.ndarray | None]:
    return [None if f is None else to_lab(shrink(f))[..., 0] for f in _read(path, indices)]


def _weights(path, indices, shape) -> list[np.ndarray | None]:
    return [None if f is None else
            cv2.resize(f[..., 0], (shape[1], shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
            for f in _read(path, indices)]


def _mean(values: list[float]) -> float | None:
    return round(float(np.mean(values)), 2) if values else None


def edge_and_flicker(take: str, output: pathlib.Path, matte: TakeMatte) -> dict[str, float | None]:
    """The output's seam and flicker, each measured relative to the raw take's own."""
    total = min(_frame_count(take), _frame_count(output))
    picks = [int(total * (i + 0.5) / SEAM_FRAMES) for i in range(SEAM_FRAMES)]
    raw, out = _lightness(take, picks), _lightness(output, picks)
    shape = next((f.shape for f in raw if f is not None), None)
    gaps: list[float] = []
    if shape is not None:
        for r, o, alpha in zip(raw, out, _weights(matte.subject, picks, shape)):
            if r is None or o is None or alpha is None:
                continue
            before, after = seam(r, alpha), seam(o, alpha)
            if before is not None and after is not None:
                gaps.append(after - before)
    room: list[float] = []
    face: list[float] = []
    for share in FLICKER_STARTS:
        start = int(total * share)
        run = list(range(start, min(total, start + FLICKER_RUN)))
        raw_run, out_run = _lightness(take, run), _lightness(output, run)
        if len(run) < 2 or any(f is None for f in raw_run + out_run):
            continue
        size = raw_run[0].shape
        alphas = _weights(matte.subject, run, size)
        skins = (_weights(matte.skin, run, size) if matte.skin
                 else [np.zeros(size, np.float32)] * len(run))
        if any(a is None for a in alphas + skins):
            continue
        result = flicker(out_run, raw_run, alphas, skins)
        if result["room"] is not None:
            room.append(result["room"])
        if result["face"] is not None:
            face.append(result["face"])
    return {"seam": _mean(gaps), "flicker_room": _mean(room), "flicker_face": _mean(face)}


def _reference_summary(fingerprint: dict) -> dict[str, float | None]:
    grade = fingerprint.get("grade") or {}
    return {name: (grade.get(name) or {}).get("value") for name in ZONE_TRAITS}


def _stills(video: str | pathlib.Path, prefix: pathlib.Path) -> None:
    duration = probe(video).duration
    for label, share in (("a", 1 / 3), ("b", 2 / 3)):
        extract_frame(video, duration * share, prefix.with_name(f"{prefix.name}_{label}.jpg"))


def evaluate_pair(take: str, matte: TakeMatte, reference: dict, out_dir: str | pathlib.Path,
                  strength: float | None = None, choke_pct: float | None = None,
                  feather_pct: float | None = None) -> dict:
    """Render `take` with today's grade and the colourist grade toward `reference`, and measure both."""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = apply_fingerprint(StyleProfile(), reference)
    if strength is not None:
        profile = profile.model_copy(update={"grade": profile.grade.model_copy(update={"strength": strength})})
    info = probe(take)
    canvas = Canvas(width=info.width // 2 * 2, height=info.height // 2 * 2, fps=info.fps)
    clip = VideoClip(src=take, start=0.0, end=info.duration)
    mattes = {take: matte}
    today = Look(mattes=mattes, skin_protect=profile.subject.skin_protect)
    baked = global_lut_for(profile, [take], out_dir)
    if baked is not None:
        today = today.model_copy(update={"lut": str(baked[0])})
    zone = zone_grade_for(profile, [take], mattes, out_dir)
    if zone is not None and (choke_pct is not None or feather_pct is not None):
        zone = zone.model_copy(update={k: v for k, v in (("choke_pct", choke_pct), ("feather_pct", feather_pct))
                                       if v is not None})
    raw_look = take_zone_look([take], mattes)
    report: dict = {"take": take, "reference": reference.get("source"),
                    "reference_summary": _reference_summary(reference), "raw": summarise(raw_look),
                    "controls": zone.controls.model_dump() if zone and zone.controls else None}
    _stills(take, out_dir / "raw")
    variants = {"today": today}
    if zone is not None:
        variants["colourist"] = today.model_copy(update={"zone_grade": zone})
    for name, look in variants.items():
        path = out_dir / f"{name}.mp4"
        started = time.monotonic()
        render(EditProgram(canvas=canvas, video=[clip], look=look), path, out_dir / f"work_{name}")
        seconds = time.monotonic() - started
        graded = take_zone_look([str(path)], {str(path): matte})
        face = (None if not (graded and graded.skin and raw_look and raw_look.skin)
                else round(graded.skin.median_l - raw_look.skin.median_l, 2))
        report[name] = {**summarise(graded), "face_l_change": face, "render_seconds": round(seconds, 1),
                        **edge_and_flicker(take, path, matte)}
        _stills(path, out_dir / name)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    return report


def _distance(trait: str, ours: float, theirs: float) -> float:
    if trait == "skin_hue":
        gap = abs(ours - theirs) % 360.0
        return min(gap, 360.0 - gap)
    return abs(ours - theirs)


def verdict(reports: list[dict]) -> dict:
    """The spec's pass bars, over every pair."""
    wins: dict[str, bool] = {}
    for trait in ZONE_TRAITS:
        gaps: dict[str, list[float]] = {"today": [], "colourist": []}
        for report in reports:
            theirs = report["reference_summary"].get(trait)
            if theirs is None or "colourist" not in report:
                continue
            for name in gaps:
                ours = report[name].get(trait)
                if ours is not None:
                    gaps[name].append(_distance(trait, ours, theirs))
        if gaps["today"] and gaps["colourist"]:
            wins[trait] = float(np.mean(gaps["colourist"])) < float(np.mean(gaps["today"]))
    zoned = [r["colourist"] for r in reports if "colourist" in r]
    within = lambda value, limit: value is None or abs(value) <= limit
    return {
        "trait_wins": wins,
        "wins": sum(wins.values()),
        "face_ok": all(within(r["face_l_change"], FACE_LIMIT) for r in zoned),
        "seam_ok": all(within(r["seam"], SEAM_LIMIT) for r in zoned),
        "flicker_ok": all(r[k] is None or r[k] <= FLICKER_LIMIT for r in zoned for k in ("flicker_room", "flicker_face")),
        "fallback_pairs": [f"{r['take']} x {r['reference']}" for r in reports if "colourist" not in r],
    }


def _cached_mattes(takes: list[str], out_dir: pathlib.Path) -> dict[str, TakeMatte]:
    found: dict[str, TakeMatte] = {}
    missing: list[str] = []
    for take in takes:
        stem = pathlib.Path(take).stem
        subject, skin = out_dir / f"{stem}.subject.mp4", out_dir / f"{stem}.skin.mp4"
        if subject.exists() and skin.exists():
            found[take] = TakeMatte(subject=str(subject.resolve()), skin=str(skin.resolve()))
        else:
            missing.append(take)
    if missing:
        found.update(matte_takes(missing, out_dir))
    return found


def _cached_fingerprint(reference: str, out_dir: pathlib.Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{pathlib.Path(reference).stem[:40]}.json"
    if path.exists():
        return json.loads(path.read_text())
    measured = extract_fingerprint(reference, stride=3).as_dict()
    path.write_text(json.dumps(measured))
    return measured


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the colourist grade against today's, takes x references.")
    parser.add_argument("--takes", nargs="+", required=True)
    parser.add_argument("--references", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cache", default="", help="where mattes and fingerprints are kept (default: --out)")
    parser.add_argument("--strength", type=float, default=None)
    parser.add_argument("--choke", type=float, default=None, help="grade matte choke, share of height")
    parser.add_argument("--feather", type=float, default=None, help="grade matte feather, share of height")
    args = parser.parse_args(argv)
    out = pathlib.Path(args.out)
    cache = pathlib.Path(args.cache) if args.cache else out
    mattes = _cached_mattes(args.takes, cache / "mattes")
    reports = []
    for reference in args.references:
        fingerprint = _cached_fingerprint(reference, cache / "references")
        for take in args.takes:
            pair = out / f"{pathlib.Path(take).stem[:24]}__{pathlib.Path(reference).stem[:24]}"
            report = evaluate_pair(take, mattes[take], fingerprint, pair,
                                   args.strength, args.choke, args.feather)
            reports.append(report)
            made = report.get("colourist")
            print(f"{pair.name}: colourist={'yes' if made else 'fallback'}"
                  + (f" face {made['face_l_change']} seam {made['seam']} "
                     f"flicker {made['flicker_room']}/{made['flicker_face']}" if made else ""))
    summary = {"pairs": reports, "verdict": verdict(reports)}
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary["verdict"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
