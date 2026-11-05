"""Talking to a language model.

Phase 7 uses Ollama, which runs open models on your own computer: free, private (the
question never leaves your machine) and good enough to translate questions into SQL.
Anything with a ``complete`` method works, so tests use a fake model and a paid API
could be added later without touching the rest of the code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

DEFAULT_URL = "http://localhost:11434"
# One general model for SQL and law. On the exam (evals/, ADR-0009) it tied the coding
# model on SQL (17/18 each, different misses) with no retries and no unverified numbers in
# its explanations, and only it cited articles reliably.
DEFAULT_MODEL = "qwen2.5:7b"


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


class LanguageModel(Protocol):
    def complete(self, messages: list[Message]) -> str:
        """Return the model's reply to the conversation."""
        ...


class LLMError(RuntimeError):
    """The model could not be reached or returned something unusable."""


class OllamaModel:
    """A model served by Ollama (https://ollama.com) through its local HTTP API."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 300.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model or os.environ.get("LUPA_LLM_MODEL", DEFAULT_MODEL)
        url = (base_url or os.environ.get("LUPA_OLLAMA_URL", DEFAULT_URL)).rstrip("/")
        self.base_url = url
        self._client = client or httpx.Client(timeout=timeout)

    def complete(self, messages: list[Message]) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            # temperature 0: the same question gives the same SQL, which we can test.
            # num_ctx: room for the schema (~2,500 tokens); older Ollama defaults to 2,048
            # and silently cuts the beginning of the prompt.
            "options": {"temperature": 0, "num_ctx": 8192},
        }
        try:
            response = self._client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise LLMError(
                f"cannot reach Ollama at {self.base_url}. Is it running? ({exc})"
            ) from exc
        if response.status_code == 404:
            raise LLMError(f"model '{self.model}' not found. Download it: ollama pull {self.model}")
        if response.status_code != 200:
            raise LLMError(f"Ollama answered HTTP {response.status_code}: {response.text[:200]}")
        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMError("unexpected answer from Ollama") from exc
        return str(content)
