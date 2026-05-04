"""Thin wrapper around the official Together AI Python SDK."""

from __future__ import annotations

import os
from typing import Any


class TogetherClient:
    """Small wrapper around Together AI's SDK used by the experiment runner."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.together.ai/v1",
        api_key: str | None = None,
        api_key_env: str = "TOGETHER_API_KEY",
        timeout_seconds: int = 600,
    ) -> None:
        """Store connection settings and resolve authentication for later API calls."""
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key or os.environ.get(api_key_env)
        if not self.api_key:
            raise ValueError(
                "Together AI requires an API key. Set TOGETHER_API_KEY or configure backend.api_key."
            )
        try:
            from together import Together
        except ImportError as exc:  # pragma: no cover - depends on optional runtime dependency.
            raise RuntimeError(
                "Together AI support requires the official SDK. Install it with `pip install together`."
            ) from exc

        self.base_url = base_url.rstrip("/")
        self._client = Together(api_key=self.api_key)

    def healthcheck(self) -> list[dict[str, Any]]:
        """Verify that the Together API is reachable by listing available models."""
        try:
            models = self._client.models.list()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Could not reach Together AI at {self.base_url}: {exc}") from exc
        return [self._to_plain_data(model) for model in models]

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Submit a non-streaming chat completion request and normalize the response."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {"model": model, "messages": messages}
        if options:
            payload.update(options)
        if response_format:
            payload["response_format"] = response_format

        try:
            completion = self._client.chat.completions.create(**payload)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Could not reach Together AI at {self.base_url}: {exc}") from exc

        raw_response = self._to_plain_data(completion)
        choice = {}
        if isinstance(raw_response.get("choices"), list) and raw_response["choices"]:
            choice = raw_response["choices"][0]

        message = choice.get("message", {})
        usage = raw_response.get("usage", {})
        response_text = message.get("content")
        if response_text is None:
            response_text = choice.get("text", "")

        return {
            "model": raw_response.get("model", model),
            "response": response_text or "",
            "done": True,
            "done_reason": choice.get("finish_reason", ""),
            "prompt_eval_count": usage.get("prompt_tokens"),
            "eval_count": usage.get("completion_tokens"),
            "total_token_count": usage.get("total_tokens"),
            "total_duration": None,
            "load_duration": None,
            "prompt_eval_duration": None,
            "eval_duration": None,
            "raw_response": raw_response,
        }

    def _to_plain_data(self, payload: Any) -> Any:
        """Convert SDK response objects into plain Python dictionaries and lists."""
        if hasattr(payload, "model_dump"):
            return payload.model_dump()
        if isinstance(payload, list):
            return [self._to_plain_data(item) for item in payload]
        return payload
