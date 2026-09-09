"""Locating the ffmpeg binaries once, so no other module hardcodes a path."""
from __future__ import annotations

import os
import shutil

_EXTRA_DIRS = ("/opt/homebrew/bin", "/usr/local/bin")


def _find(name: str, env_var: str) -> str:
    override = os.environ.get(env_var)
    if override:
        return override
    found = shutil.which(name)
    if found:
        return found
    for directory in _EXTRA_DIRS:
        candidate = os.path.join(directory, name)
        if os.path.exists(candidate):
            return candidate
    raise RuntimeError(f"{name} not found on PATH; install it or set {env_var}")


def ffmpeg() -> str:
    return _find("ffmpeg", "FFMPEG")


def ffprobe() -> str:
    return _find("ffprobe", "FFPROBE")
