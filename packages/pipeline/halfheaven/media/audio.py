"""Pulling an audio track out of a video for transcription."""
from __future__ import annotations

import pathlib
import subprocess

from halfheaven.media.ffmpeg_bin import ffmpeg
from halfheaven.media.probe import probe

SAMPLE_RATE = 16000


def extract_audio(video: str | pathlib.Path, out_path: str | pathlib.Path) -> pathlib.Path:
    """Mono 16kHz PCM, which is what Whisper wants and is small to upload.

    Raises if the video has no audio track. Writing a silent file instead would
    transcribe to nothing and read as a model failure rather than as the missing
    track it actually is.
    """
    video, out_path = pathlib.Path(video), pathlib.Path(out_path)
    if not probe(video).has_audio:
        raise ValueError(f"{video.name} has no audio track to extract")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ffmpeg(), "-v", "error", "-y", "-i", str(video), "-vn",
         "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path
