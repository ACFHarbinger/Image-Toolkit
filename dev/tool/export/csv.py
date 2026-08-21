"""CSV export: the session's raw events as a flat table."""

from __future__ import annotations

import csv
import io
from typing import List

_COLUMNS = ["t", "pid", "tid", "tname", "category", "event"]


def events_to_csv(events: List[dict]) -> str:
    """Serialize events to CSV text. Extra fields are folded into a final
    'fields' column (key=value, space-separated) so no data is dropped."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_COLUMNS + ["fields"])
    for e in events:
        row = [e.get(col, "") for col in _COLUMNS]
        extra = {
            k: v
            for k, v in e.items()
            if k not in _COLUMNS and k != "wall"
        }
        row.append(" ".join(f"{k}={v!r}" for k, v in extra.items()))
        writer.writerow(row)
    return buf.getvalue()


__all__ = ["events_to_csv"]
