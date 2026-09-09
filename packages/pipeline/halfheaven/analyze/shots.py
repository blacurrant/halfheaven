"""Shot boundary detection and the pacing profile derived from it.

Pacing is the highest-confidence signal we can recover from a rendered video,
and it needs no audio - which is why it is the backbone of the StyleProfile.
"""
from __future__ import annotations

import pathlib
import statistics
from dataclasses import dataclass

from scenedetect import ContentDetector, detect

from halfheaven.media.probe import probe

DEFAULT_THRESHOLD = 27.0


@dataclass(frozen=True)
class Shot:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class Pacing:
    shot_count: int
    median_shot: float
    p10_shot: float
    p90_shot: float
    cuts_per_min: float
    total_duration: float


def detect_shots(path: str | pathlib.Path, threshold: float = DEFAULT_THRESHOLD) -> list[Shot]:
    """Shot list for a video. Always at least one shot.

    scenedetect returns an empty list for a video it finds no cuts in. That is
    not the same as "no shots" - a continuous take is one shot - and downstream
    pacing maths divides by the count, so we normalise here.
    """
    path = pathlib.Path(path)
    duration = probe(path).duration
    scenes = detect(str(path), ContentDetector(threshold=threshold))
    if not scenes:
        return [Shot(start=0.0, end=duration)]
    return [Shot(start=start.seconds, end=end.seconds) for start, end in scenes]


def pacing(shots: list[Shot]) -> Pacing:
    durations = sorted(s.duration for s in shots)
    total = sum(durations)
    cuts = max(0, len(shots) - 1)
    return Pacing(
        shot_count=len(shots),
        median_shot=statistics.median(durations) if durations else 0.0,
        p10_shot=_percentile(durations, 0.10),
        p90_shot=_percentile(durations, 0.90),
        cuts_per_min=(60.0 * cuts / total) if total else 0.0,
        total_duration=total,
    )


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    index = fraction * (len(sorted_values) - 1)
    low = int(index)
    high = min(low + 1, len(sorted_values) - 1)
    weight = index - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight
