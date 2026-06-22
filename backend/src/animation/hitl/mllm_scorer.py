"""§3.10 — MLLM semantic quality scoring for anime stitch composites.

Scores a composite image on four anime-specific axes using a vision-language
model (Qwen2-VL-7B via ollama).  Zero-installs: calls the ollama REST API.

Enable: ASP_MLLM_SCORER=1  (default OFF — requires ollama running locally)
Model:  ASP_MLLM_MODEL=qwen2-vl:7b  (any multimodal ollama model)
"""

from __future__ import annotations

import base64
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from backend.src.constants.animation import MLLM_MAX_IMAGE_DIM, MLLM_TIMEOUT_SEC

logger = logging.getLogger(__name__)

__all__ = [
    "MllmScores",
    "MllmScorer",
    "score_composite",
    "MLLM_MAX_IMAGE_DIM",
    "MLLM_TIMEOUT_SEC",
]

_PROMPT = """\
Rate this anime composite panorama on four axes (0=worst, 10=best). Reply ONLY with JSON:
{
  "body_coherence": <float 0-10>,
  "seam_quality": <float 0-10>,
  "bg_consistency": <float 0-10>,
  "overall": <float 0-10>
}

body_coherence: character bodies are complete, proportional, and not split or duplicated
seam_quality: no visible seam line, no double-image ghost artifacts where frames join
bg_consistency: background continues smoothly with no abrupt cuts or repeated content
overall: holistic quality of the full panorama"""


@dataclass
class MllmScores:
    body_coherence: Optional[float] = None
    seam_quality: Optional[float] = None
    bg_consistency: Optional[float] = None
    overall: Optional[float] = None
    raw_response: str = field(default="", repr=False)


class MllmScorer:
    def __init__(
        self,
        model: str = "qwen2-vl:7b",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self._base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            return any(self._model in m.get("name", "") for m in data.get("models", []))
        except Exception:
            return False

    def _encode_image(self, image_bgr: np.ndarray) -> str:
        h, w = image_bgr.shape[:2]
        longest = max(h, w)
        if longest > MLLM_MAX_IMAGE_DIM:
            scale = MLLM_MAX_IMAGE_DIM / longest
            image_bgr = cv2.resize(
                image_bgr,
                (max(1, int(w * scale)), max(1, int(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("cv2.imencode failed")
        return base64.b64encode(buf.tobytes()).decode("ascii")

    def _parse_scores(self, raw: str) -> MllmScores:
        keys = ("body_coherence", "seam_quality", "bg_consistency", "overall")
        # Try JSON parse first; look for the innermost {...} block
        match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group())
                vals = {k: float(obj[k]) for k in keys if k in obj}
                if vals:
                    return MllmScores(
                        **{k: vals.get(k) for k in keys}, raw_response=raw
                    )
            except (json.JSONDecodeError, ValueError):
                pass
        # Regex fallback: "key": 7.5  or  key: 7.5
        vals = {}
        for k in keys:
            m = re.search(rf'"{k}"\s*:\s*([0-9]+(?:\.[0-9]+)?)', raw)
            if not m:
                m = re.search(rf"{k}\s*:\s*([0-9]+(?:\.[0-9]+)?)", raw)
            if m:
                vals[k] = float(m.group(1))
        return MllmScores(**{k: vals.get(k) for k in keys}, raw_response=raw)

    def score(self, image_bgr: np.ndarray) -> MllmScores:
        try:
            encoded = self._encode_image(image_bgr)
        except Exception as exc:
            logger.warning("[MllmScorer] Image encode failed: %s", exc)
            return MllmScores()

        payload = json.dumps(
            {
                "model": self._model,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": _PROMPT,
                        "images": [encoded],
                    }
                ],
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=MLLM_TIMEOUT_SEC) as resp:
                body = json.loads(resp.read())
            raw = body.get("message", {}).get("content", "")
            return self._parse_scores(raw)
        except Exception as exc:
            logger.warning("[MllmScorer] Request failed: %s", exc)
            return MllmScores()


def score_composite(
    image_bgr: np.ndarray,
    model: str = "qwen2-vl:7b",
    base_url: str = "http://localhost:11434",
) -> MllmScores:
    return MllmScorer(model=model, base_url=base_url).score(image_bgr)
