"""
hf_client.py
------------
The optional *cloud* AI brain, powered by the Hugging Face Inference API.

Why cloud here (and not for reeling)?
  - Reeling needs <50 ms reactions -> stays 100% local OpenCV.
  - Deciding "is this a GOOD catch?" happens once per fish (~every 30 s), so a
    1-3 s network call is totally fine. This is where a real model helps, and it
    runs on Hugging Face's servers -> no good PC / GPU required on your end.

It supports two Inference API tasks (chosen in config.json -> huggingface.task):
  * "zero-shot-image-classification"  (default, e.g. CLIP)
        You give candidate_labels like ["a rare fish", "a common fish", "junk"]
        and the model scores the screenshot against each -> no custom training.
  * "image-classification"
        A normal classifier that returns its own label set.

The token is read from config.json (huggingface.api_token) OR the HF_API_TOKEN
environment variable. It is never printed or written anywhere by this tool.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import List, Optional

try:
    import requests
except Exception:  # pragma: no cover - requests is a hard dep, but stay safe
    requests = None


@dataclass
class CatchVerdict:
    label: str
    score: float
    is_good: bool
    raw: object = None


class HuggingFaceBrain:
    def __init__(self, cfg: dict) -> None:
        hc = cfg.get("huggingface", {})
        self.enabled = bool(hc.get("enabled", False))
        self.task = hc.get("task", "zero-shot-image-classification")
        self.model = hc.get("model", "openai/clip-vit-large-patch14")
        self.endpoint = hc.get("endpoint",
                               "https://api-inference.huggingface.co/models/")
        self.timeout = float(hc.get("timeout_seconds", 15))
        self.candidate_labels: List[str] = list(hc.get("candidate_labels", []))
        self.good_labels = set(hc.get("good_labels", []))
        self.min_confidence = float(hc.get("min_confidence", 0.45))

        # Token: prefer env var, then config. Never stored/logged by us.
        self.token = os.environ.get("HF_API_TOKEN") or hc.get("api_token", "")

        self._url = self.endpoint.rstrip("/") + "/" + self.model
        self._ready = self._check_ready()

    def _check_ready(self) -> bool:
        if not self.enabled:
            return False
        if requests is None:
            print("[HF] 'requests' not installed -> cloud brain disabled.")
            return False
        if not self.token:
            print("[HF] No API token (config.huggingface.api_token or "
                  "HF_API_TOKEN env). Cloud brain disabled; keeping all catches.")
            return False
        return True

    @property
    def ready(self) -> bool:
        return self._ready

    # --------------------------------------------------------------------
    def classify_catch(self, image_png: bytes) -> Optional[CatchVerdict]:
        """Send a PNG screenshot of the catch to HF and return a verdict.

        Returns None on any failure (network, rate-limit, model warm-up, etc.)
        so the caller can safely fall back to 'keep the catch'."""
        if not self._ready or not image_png:
            return None
        try:
            if self.task == "zero-shot-image-classification":
                results = self._zero_shot(image_png)
            else:
                results = self._image_classification(image_png)
        except Exception as exc:
            print(f"[HF] request failed ({exc}); keeping catch.")
            return None

        if not results:
            return None

        top = results[0]
        label = str(top.get("label", "?"))
        score = float(top.get("score", 0.0))
        is_good = label in self.good_labels and score >= self.min_confidence
        return CatchVerdict(label=label, score=score, is_good=is_good, raw=results)

    # --------------------------------------------------------------------
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def _zero_shot(self, image_png: bytes) -> list:
        payload = {
            "inputs": base64.b64encode(image_png).decode("utf-8"),
            "parameters": {"candidate_labels": self.candidate_labels},
        }
        r = requests.post(self._url, headers=self._headers(),
                          json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        # API returns a list of {label, score}, already sorted by score.
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return sorted(data, key=lambda d: d.get("score", 0.0), reverse=True)
        return []

    def _image_classification(self, image_png: bytes) -> list:
        r = requests.post(self._url, headers=self._headers(),
                          data=image_png, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return sorted(data, key=lambda d: d.get("score", 0.0), reverse=True)
        return []
