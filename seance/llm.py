"""Tiny Ollama client: stdlib only, talks to a model on localhost."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional, Tuple

DEFAULT_MODEL = os.environ.get("SEANCE_MODEL", "llama3.2:3b")


def normalize_host(host: Optional[str]) -> str:
    host = host or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    if not host.startswith("http"):
        host = "http://" + host
    return host.rstrip("/")


class Medium:
    """The channel to the spirit world (a local open-weight model)."""

    def __init__(self, model: str = DEFAULT_MODEL, host: Optional[str] = None, timeout: int = 120):
        self.model = model
        self.host = normalize_host(host)
        self.timeout = timeout

    def check(self) -> Tuple[bool, str]:
        """Return (ready, message)."""
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=3) as r:
                tags = json.load(r)
        except (urllib.error.URLError, OSError, ValueError):
            return False, f"no Ollama server at {self.host} (start it with `ollama serve`)"
        names = [m.get("name", "") for m in tags.get("models", [])]
        if not any(n == self.model or n.split(":")[0] == self.model for n in names):
            return False, f"model '{self.model}' not pulled (run `ollama pull {self.model}`)"
        return True, f"ollama/{self.model} @ {self.host}"

    def channel(self, system: str, prompt: str, max_tokens: int = 140, temperature: float = 0.9) -> str:
        body = json.dumps({
            "model": self.model, "system": system, "prompt": prompt, "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }).encode()
        req = urllib.request.Request(f"{self.host}/api/generate", body,
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.load(r).get("response", "").strip()
