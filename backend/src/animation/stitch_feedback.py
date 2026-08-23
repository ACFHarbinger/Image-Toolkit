"""
backend/src/animation/stitch_feedback.py
========================================
Logger and reader for ASP / Stitching quality feedback ratings (RLHF).
Writes rating records to ~/.image-toolkit/stitch_feedback.jsonl.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from backend.src.constants.paths import IMAGE_TOOLKIT_DIR

logger = logging.getLogger(__name__)

FEEDBACK_FILE = IMAGE_TOOLKIT_DIR / "stitch_feedback.jsonl"


def log_stitch_feedback(
    test_id: str,
    user_rating: int,
    engine: str = "asp",
    asp_score: Optional[float] = None,
    simple_score: Optional[float] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record a user quality rating (1-5 stars or binary vote) for a stitching output.

    Args:
        test_id: Dataset identifier or output filename.
        user_rating: Integer rating (e.g. 1 to 5).
        engine: Engine used ('asp', 'opencv', 'hugin', 'overmix').
        asp_score: Optional ASP algorithm score.
        simple_score: Optional comparator score.
        metrics: Optional dictionary of detailed quality metrics.

    Returns:
        Dict representing the recorded feedback record.
    """
    record: Dict[str, Any] = {
        "timestamp": time.time(),
        "test_id": test_id,
        "engine": engine,
        "user_rating": user_rating,
        "asp_score": asp_score,
        "simple_score": simple_score,
        "metrics": metrics or {},
    }

    try:
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        logger.info(f"Recorded stitch feedback for {test_id}: {user_rating} stars")
    except Exception as exc:
        logger.error(f"Failed to log stitch feedback to {FEEDBACK_FILE}: {exc}")

    return record


def load_stitch_feedback() -> List[Dict[str, Any]]:
    """Load all recorded stitch feedback entries from the JSONL log file.

    Returns:
        List of recorded feedback dictionaries.
    """
    records: List[Dict[str, Any]] = []
    if not FEEDBACK_FILE.exists():
        return records

    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except Exception as exc:
        logger.warning(f"Error reading stitch feedback log {FEEDBACK_FILE}: {exc}")

    return records


__all__ = ["FEEDBACK_FILE", "log_stitch_feedback", "load_stitch_feedback"]
