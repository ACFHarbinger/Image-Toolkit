"""Preference-vote logging for the future LocalDPO/LoRA alignment pipeline
(roadmap §6.3/§4.1/§4.2, issue #197).

The Preference Review Dialog (`gui/src/components/manga_preference_dialog.py`)
is built as a stub ahead of the DPO/LoRA alignment pipeline itself -- per the
roadmap's own "build early" rationale, preference data collection should
start as soon as any generative colorization mode ships, rather than being
retrofitted once the training loop exists. This module is that stub's
storage layer: every A/B vote is appended as one JSON line to a local log
file, immediately readable (via :func:`read_preferences`) by whatever future
training script consumes it, with no schema migration step needed to adopt
it later.

A flat JSON-lines file was chosen over SQLite (the roadmap's own text says
"SQLite/JSON") because an append-only vote log has no query/update/deletion
requirements -- SQLite's transactional guarantees and query engine would be
unused machinery for a workload that's just "append a record, read them all
back later." JSONL is human-inspectable, needs no new dependency, and is
trivially concatenable if preference logs from multiple installs are ever
merged for training.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal

__all__ = ["DEFAULT_PREFERENCE_LOG_PATH", "log_preference", "read_preferences"]

# Same ~/.image-toolkit/ convention as gui/src/constants/utils.py's
# _KEYBINDINGS_PATH -- this project's established local-app-data location.
DEFAULT_PREFERENCE_LOG_PATH = Path.home() / ".image-toolkit" / "manga_preferences.jsonl"

Winner = Literal["a", "b", "tie"]


def log_preference(
    source_a: str,
    source_b: str,
    winner: Winner,
    metadata: dict[str, Any] | None = None,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Append one preference vote to the local JSON-lines log.

    Args:
        source_a: identifier for candidate A (e.g. a file path, or a
            "<mode> @ <timestamp>" label) -- whatever lets a later reader
            locate/regenerate the actual candidate image.
        source_b: identifier for candidate B, same contract as ``source_a``.
        winner: ``"a"``, ``"b"``, or ``"tie"``.
        metadata: optional extra context to store alongside the vote (e.g.
            which colorization modes produced each candidate, the source
            line-art path). Stored as-is, not interpreted.
        log_path: overrides :data:`DEFAULT_PREFERENCE_LOG_PATH` (mainly for
            tests).

    Returns:
        The record that was written (including its ``timestamp``).
    """
    if winner not in ("a", "b", "tie"):
        raise ValueError(f"winner must be 'a', 'b', or 'tie', got {winner!r}")

    record: dict[str, Any] = {
        "timestamp": time.time(),
        "source_a": source_a,
        "source_b": source_b,
        "winner": winner,
        "metadata": metadata or {},
    }

    path = log_path or DEFAULT_PREFERENCE_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return record


def read_preferences(log_path: Path | None = None) -> list[dict[str, Any]]:
    """Read back every vote recorded so far, oldest first.

    Returns an empty list if the log doesn't exist yet, rather than raising
    -- reading before the first vote is a normal, not exceptional, case for
    a future training script polling this file.
    """
    path = log_path or DEFAULT_PREFERENCE_LOG_PATH
    if not path.exists():
        return []

    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
