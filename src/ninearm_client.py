from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class NineArmClient:
    base_url: str
    api_key: str
    primary_model: str
    fallback_model: str

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def list_models(self) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url.rstrip('/')}/models",
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers=self._headers(),
            json={
                "model": model or self.primary_model,
                "messages": messages,
            },
            timeout=90,
        )
        response.raise_for_status()
        return response.json()

    def embeddings(self, inputs: list[str], model: str) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url.rstrip('/')}/embeddings",
            headers=self._headers(),
            json={"model": model, "input": inputs},
            timeout=90,
        )
        response.raise_for_status()
        return response.json()
