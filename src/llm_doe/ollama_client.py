"""Minimal HTTP client for interacting with the Ollama generate API."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class OllamaClient:
    """Small wrapper around Ollama's REST API used by the experiment runner."""

    def __init__(self, base_url: str, timeout_seconds: int = 600) -> None:
        """Store connection settings for later API calls."""
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def healthcheck(self) -> dict[str, Any]:
        """Verify that the Ollama server is reachable and return its tag listing."""
        request = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict[str, Any] | None = None,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        """Submit a non-streaming generation request and return the decoded JSON response."""
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options
        if response_format == "json":
            payload["format"] = "json"

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
