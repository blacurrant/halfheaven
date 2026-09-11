"""What is this file? Asked once per input, before any other stage runs."""
from __future__ import annotations

import json
import pathlib
import subprocess
from dataclasses import dataclass

from halfheaven.media.ffmpeg_bin import ffprobe


@dataclass(frozen=True)
class MediaInfo:
    path: pathlib.Path
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    has_audio: bool
    audio_sample_rate: int | None = None
    audio_channels: int | None = None

    @property
    def is_vertical(self) -> bool:
        return self.height > self.width

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 0.0


def _fraction(value: str | None) -> float:
    """ffprobe reports frame rates as 'num/den'."""
    if not value:
        return 0.0
    if "/" in value:
        numerator, _, denominator = value.partition("/")
        denom = float(denominator)
        return float(numerator) / denom if denom else 0.0
    return float(value)


def _rotation(video: dict) -> int:
    """Display rotation in degrees, from side data or the legacy `rotate` tag.

    Phones store a portrait clip as landscape pixels plus an instruction to turn
    them. ffmpeg's decoder and OpenCV both obey it, so every frame anyone reads
    is portrait - while the stream's `width` and `height` still describe the
    unrotated pixels.
    """
    for item in video.get("side_data_list") or []:
        if "rotation" in item:
            try:
                return int(round(float(item["rotation"])))
            except (TypeError, ValueError):
                pass
    try:
        return int(round(float((video.get("tags") or {}).get("rotate", 0))))
    except (TypeError, ValueError):
        return 0


def probe(path: str | pathlib.Path) -> MediaInfo:
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no such media file: {path}")

    result = subprocess.run(
        [ffprobe(), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])

    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError(f"no video stream in {path}")
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = float(payload.get("format", {}).get("duration") or video.get("duration") or 0.0)

    # Report the picture as it is seen, not as it is stored. Every consumer -
    # the canvas, the reframe check, the renderer's crop - wants display size,
    # and a rotated phone clip read as landscape gets squashed or turned sideways.
    width, height = int(video["width"]), int(video["height"])
    if _rotation(video) % 180:
        width, height = height, width

    return MediaInfo(
        path=path,
        duration=duration,
        width=width,
        height=height,
        fps=_fraction(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        video_codec=video.get("codec_name", ""),
        has_audio=audio is not None,
        audio_sample_rate=int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        audio_channels=int(audio["channels"]) if audio and audio.get("channels") else None,
    )
