from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class OllamaWarehouseModel:
    """
    Adapter for local Ollama server.

    Env vars:
    - OLLAMA_BASE_URL (default: http://127.0.0.1:11434)
    - OLLAMA_MODEL (optional; if empty, first installed model will be used)
    """

    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.model_name = (os.getenv("OLLAMA_MODEL") or "").strip()

        self._healthcheck()
        if not self.model_name:
            self.model_name = self._pick_first_installed_model()
        if not self.model_name:
            raise RuntimeError("No installed Ollama models found. Run: ollama pull <model>")

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        }
        data = self._post_json("/api/generate", payload)
        text = (data.get("response") or "").strip()
        return text

    def _healthcheck(self) -> None:
        try:
            self._get_json("/api/tags")
        except Exception as exc:
            raise RuntimeError(
                "Ollama is not reachable. Start it first: `ollama serve`."
            ) from exc

    def _pick_first_installed_model(self) -> Optional[str]:
        data = self._get_json("/api/tags")
        models = data.get("models") or []
        if not models:
            return None
        first = models[0] or {}
        return (first.get("name") or "").strip() or None

    def _get_json(self, path: str) -> Dict[str, Any]:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            method="GET",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Ollama HTTP error {exc.code} for {path}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ollama URL error for {path}: {exc}") from exc

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        encoded = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=encoded,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Ollama HTTP error {exc.code} for {path}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ollama URL error for {path}: {exc}") from exc
