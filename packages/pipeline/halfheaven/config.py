"""Runtime config. Secrets come from .env.local, never from source."""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass


def _load_env_local() -> None:
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        env = parent / ".env.local"
        if env.exists():
            for line in env.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())
            return


@dataclass(frozen=True)
class Config:
    api_key: str
    asr_model: str
    llm_model: str
    vision_model: str
    base_url: str = "https://api.groq.com/openai/v1"

    @classmethod
    def load(cls) -> "Config":
        _load_env_local()
        key = os.environ.get("GROQ_API_KEY", "")
        if not key:
            raise RuntimeError("GROQ_API_KEY missing - set it in .env.local at the repo root")
        return cls(
            api_key=key,
            # Groq rotates model IDs; these are pinned and verified at boot.
            asr_model=os.environ.get("GROQ_MODEL_ASR", "whisper-large-v3-turbo"),
            llm_model=os.environ.get("GROQ_MODEL_LLM", "openai/gpt-oss-120b"),
            vision_model=os.environ.get("GROQ_MODEL_VISION", "qwen/qwen3.8-27b"),
        )
