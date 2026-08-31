"""Durable append-only store of cloud-job :class:`UsageRow` records (#487).

One JSON object per line at ``~/.image-toolkit/cloud_usage.jsonl``. The Cloud
Compute *Dashboards* tab reads this back through ``load_rows()`` and feeds it
to ``aggregate_usage_rows`` (#490). Qt-free.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import List, Optional

from backend.src.constants import IMAGE_TOOLKIT_DIR

from .usage import UsageRow

DEFAULT_USAGE_PATH = Path(IMAGE_TOOLKIT_DIR) / "cloud_usage.jsonl"


class UsageStore:
    def __init__(self, path: Optional[os.PathLike | str] = None) -> None:
        self._path = Path(path) if path is not None else DEFAULT_USAGE_PATH

    @property
    def path(self) -> Path:
        return self._path

    def append(self, row: UsageRow) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "job_id": row.job_id,
            "provider": row.provider,
            "task": row.task,
            "status": row.status,
            "duration_seconds": row.duration_seconds,
            "timestamp": row.timestamp,
            "peak_rss_kib": row.peak_rss_kib,
            "peak_vcpu": row.peak_vcpu,
            "peak_gpu": row.peak_gpu,
            "egress_bytes": row.egress_bytes,
            "cost_usd": row.cost_usd,
        }
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_rows(self) -> List[UsageRow]:
        if not self._path.exists():
            return []
        rows: List[UsageRow] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(UsageRow.from_mapping(json.loads(line)))
            except (ValueError, TypeError):
                continue  # skip a corrupt line rather than lose the rest
        return rows

    def clear(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            self._path.unlink()


__all__ = ["UsageStore", "DEFAULT_USAGE_PATH"]
