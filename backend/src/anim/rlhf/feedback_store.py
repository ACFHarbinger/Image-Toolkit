"""
RLHF feedback persistence.

Each feedback record is one JSON line in  ~/.config/image-toolkit/rlhf_feedback.jsonl
so the file can be appended to without locking and inspected with standard tools.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional

# ---------------------------------------------------------------------------
# Flaw taxonomy
# ---------------------------------------------------------------------------

FLAW_TYPES = [
    "seam",
    "blur",
    "misalignment",
    "color_mismatch",
    "dark_border",
    "compression",
    "ghosting",
]

_STORE_PATH = Path.home() / ".config" / "image-toolkit" / "rlhf_feedback.jsonl"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class StitchAnnotation:
    """One human-drawn bounding box indicating a flaw region."""
    x: float         # normalized [0, 1] — left edge
    y: float         # normalized [0, 1] — top edge
    w: float         # normalized [0, 1] — width
    h: float         # normalized [0, 1] — height
    flaw_type: str   # one of FLAW_TYPES
    severity: float  # [0, 1]; 0 = barely noticeable, 1 = unusable
    description: str = ""


@dataclass
class StitchFeedback:
    """Complete human feedback for a single stitched panorama."""
    image_path: str
    image_hash: str          # MD5 of the file bytes (stable identifier)
    overall_rating: float    # [0, 10] — 0 = worst, 10 = perfect
    annotations: List[StitchAnnotation] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    pipeline_config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StitchFeedback":
        annotations = [StitchAnnotation(**a) for a in d.pop("annotations", [])]
        return cls(annotations=annotations, **d)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class FeedbackStore:
    """Append-only JSONL store for stitch quality feedback."""

    def __init__(self, path: Optional[str] = None):
        self._path = Path(path) if path else _STORE_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------- write

    def add(self, feedback: StitchFeedback) -> None:
        """Append one feedback record atomically (a single line write)."""
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback.to_dict(), ensure_ascii=False) + "\n")

    def add_from_image(
        self,
        image_path: str,
        overall_rating: float,
        annotations: Optional[List[StitchAnnotation]] = None,
        pipeline_config: Optional[dict] = None,
    ) -> StitchFeedback:
        """Convenience: hash the image, build a feedback record, and store it."""
        fb = StitchFeedback(
            image_path=image_path,
            image_hash=_md5(image_path),
            overall_rating=float(overall_rating),
            annotations=annotations or [],
            pipeline_config=pipeline_config or {},
        )
        self.add(fb)
        return fb

    # ------------------------------------------------------------------ read

    def __iter__(self) -> Iterator[StitchFeedback]:
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield StitchFeedback.from_dict(json.loads(line))
                except Exception:
                    pass  # skip malformed lines

    def all(self) -> List[StitchFeedback]:
        return list(self)

    def count(self) -> int:
        return sum(1 for _ in self)

    @property
    def path(self) -> Path:
        return self._path


__all__ = ["FeedbackStore", "StitchFeedback", "StitchAnnotation", "FLAW_TYPES"]
