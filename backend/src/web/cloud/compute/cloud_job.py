"""`CloudJob` — the canonical, Qt-free description of one heavy request.

`to_job_json()` is the single source of truth for the provider-worker wire
schema; keep it in lock-step with ``infra/cloud/gcd/worker/extraction.py``
(``ExtractionJob.from_json``). Validation here mirrors the worker so a bad
job fails on the client before anything is uploaded or dispatched.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

_VALID_MODES = ("range", "gif", "video")
_FPS_MIN, _FPS_MAX = 1, 120

# extractor-tab queue "type" -> cloud worker "mode"
_TYPE_TO_MODE = {"range": "range", "gif": "gif", "video": "video", "single": "range"}


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value) or "job"


@dataclass(frozen=True)
class CloudJob:
    """One heavy request destined for a cloud provider worker.

    ``source_uri`` is where the worker reads the input from (a ``gs://`` object
    for the GCD PoC). The local file is uploaded there first by the caller;
    this model deliberately does not do IO.
    """

    source_uri: str
    mode: str = "range"
    start_ms: int = 0
    end_ms: int = 0
    fps: int = 24
    target_size: Optional[Tuple[int, int]] = None
    job_id: str = field(default_factory=lambda: f"job-{uuid.uuid4().hex[:12]}")
    output_prefix: str = ""
    task: str = "extract"
    # provider-specific / forward-compat extras, passed through verbatim
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", _slug(str(self.job_id)))
        object.__setattr__(self, "mode", str(self.mode).lower())
        object.__setattr__(self, "start_ms", int(self.start_ms))
        object.__setattr__(self, "end_ms", int(self.end_ms))
        object.__setattr__(
            self, "fps", max(_FPS_MIN, min(int(self.fps), _FPS_MAX))
        )
        if self.target_size is not None:
            w, h = self.target_size
            object.__setattr__(
                self, "target_size", (max(1, int(w)), max(1, int(h)))
            )
        if not self.output_prefix:
            object.__setattr__(self, "output_prefix", f"cloud-jobs/{self.job_id}")

        # --- validation (mirrors the worker) ---
        if self.mode not in _VALID_MODES:
            raise ValueError(f"mode must be one of {_VALID_MODES}, got {self.mode!r}")
        if not str(self.source_uri):
            raise ValueError("source_uri is required")
        if self.start_ms < 0:
            raise ValueError("start_ms must be >= 0")
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")

    # ------------------------------------------------------------------ wire
    def to_job_json(self) -> Dict[str, Any]:
        """The exact payload a provider worker's ``/jobs`` endpoint expects."""
        payload: Dict[str, Any] = {
            "job_id": self.job_id,
            "source_uri": self.source_uri,
            "mode": self.mode,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "fps": self.fps,
            "output_prefix": self.output_prefix,
            "task": self.task,
        }
        if self.target_size is not None:
            payload["target_size"] = [self.target_size[0], self.target_size[1]]
        if self.extra:
            payload["extra"] = dict(self.extra)
        return payload

    # -------------------------------------------------------------- builders
    @classmethod
    def from_extraction_config(
        cls,
        config: Mapping[str, Any],
        *,
        source_uri: str,
        job_id: Optional[str] = None,
        output_prefix: str = "",
    ) -> "CloudJob":
        """Build from an extractor-tab queue config dict (``type`` / ``start_ms``
        / ``end_ms`` / ``fps`` / ``target_resolution``)."""
        raw_type = str(config.get("type", "range")).lower()
        mode = _TYPE_TO_MODE.get(raw_type, "range")
        start_ms = int(config.get("start_ms", 0) or 0)
        end_ms = int(config.get("end_ms", 0) or 0)
        # A "single" frame or an open-ended (-1) range needs a bounded window
        # for the cloud worker; give it one frame at the target fps.
        fps = int(config.get("fps", 24) or 24)
        if raw_type == "single" or end_ms <= start_ms:
            end_ms = start_ms + max(1, round(1000 / max(1, fps)))
        size = config.get("target_resolution") or config.get("target_size")
        target_size = None
        if isinstance(size, (list, tuple)) and len(size) == 2:
            target_size = (int(size[0]), int(size[1]))
        return cls(
            source_uri=source_uri,
            mode=mode,
            start_ms=start_ms,
            end_ms=end_ms,
            fps=fps,
            target_size=target_size,
            job_id=job_id or f"job-{uuid.uuid4().hex[:12]}",
            output_prefix=output_prefix,
        )

    @classmethod
    def from_ui_payload(
        cls, payload: Mapping[str, Any], *, source_uri: str
    ) -> "CloudJob":
        """Build from the Cloud Compute *Request Builder* pane's payload
        (``task_type`` / ``resolution`` string / ``start_ms`` / ``end_ms``)."""
        task_type = str(payload.get("task_type", "")).lower()
        mode = "gif" if "gif" in task_type else "video" if "video" in task_type else "range"
        target_size = None
        res = str(payload.get("resolution", "")).lower()
        match = re.match(r"\s*(\d+)\s*[x×]\s*(\d+)\s*", res)
        if match:
            target_size = (int(match.group(1)), int(match.group(2)))
        return cls(
            source_uri=source_uri,
            mode=mode,
            start_ms=int(payload.get("start_ms", 0) or 0),
            end_ms=int(payload.get("end_ms", 0) or 0),
            fps=int(payload.get("fps", 24) or 24),
            target_size=target_size,
            job_id=str(payload.get("job_id") or f"job-{uuid.uuid4().hex[:12]}"),
        )


__all__ = ["CloudJob"]
