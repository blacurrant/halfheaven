"""Thin Groq transport. No business logic lives here."""
from __future__ import annotations

import base64
import json
import pathlib
from typing import Any

import requests

from halfheaven.config import Config
from halfheaven.groq.asr import Transcript, parse_transcript


class GroqError(RuntimeError):
    pass


class GroqClient:
    def __init__(self, config: Config | None = None, timeout: int = 120) -> None:
        self.config = config or Config.load()
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {self.config.api_key}"

    def _post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._session.post(
            f"{self.config.base_url}{path}", timeout=self.timeout, **kwargs
        )
        if response.status_code >= 400:
            raise GroqError(f"{response.status_code} {path}: {response.text[:500]}")
        return response.json()

    def available_models(self) -> set[str]:
        response = self._session.get(f"{self.config.base_url}/models", timeout=self.timeout)
        response.raise_for_status()
        return {m["id"] for m in response.json()["data"]}

    def verify_models(self) -> None:
        """Fail loudly at boot if Groq has rotated a model out from under us."""
        available = self.available_models()
        pinned = {
            "asr": self.config.asr_model,
            "llm": self.config.llm_model,
            "vision": self.config.vision_model,
        }
        missing = {role: name for role, name in pinned.items() if name not in available}
        if missing:
            raise GroqError(f"pinned models no longer on Groq: {missing}")

    def transcribe(self, audio: pathlib.Path) -> Transcript:
        with open(audio, "rb") as handle:
            payload = self._post(
                "/audio/transcriptions",
                files={"file": (audio.name, handle)},
                data={
                    "model": self.config.asr_model,
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": ["word", "segment"],
                },
            )
        return parse_transcript(payload)

    def chat_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 8000,
        reasoning_effort: str | None = "low",
    ) -> dict[str, Any]:
        # gpt-oss is a reasoning model: without a generous ceiling and a low
        # effort setting it spends the budget thinking and returns empty JSON.
        body: dict[str, Any] = {}
        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort
        payload = self._post(
            "/chat/completions",
            json={
                **body,
                "model": self.config.llm_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        return json.loads(payload["choices"][0]["message"]["content"])

    def vision_json(self, prompt: str, images: list[pathlib.Path]) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image in images:
            b64 = base64.b64encode(image.read_bytes()).decode()
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            )
        payload = self._post(
            "/chat/completions",
            json={
                "model": self.config.vision_model,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": content}],
            },
        )
        return json.loads(payload["choices"][0]["message"]["content"])
