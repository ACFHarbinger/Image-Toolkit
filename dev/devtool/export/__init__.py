"""devtool export surface: JSON sidecar, CSV, standalone HTML."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from debugtool import Session

from .csv import events_to_csv
from .html import session_to_html
from .json_sidecar import session_to_dict, write_sidecar


def export_session(session: Session, fmt: str = "json", out: Optional[Path] = None) -> str:
    """Serialize a session in the requested format; returns the text (and,
    if out is given, writes it to that path). Formats: json | csv | html."""
    fmt = fmt.lower()
    if fmt == "json":
        import json

        text = json.dumps(session_to_dict(session), indent=2)
    elif fmt == "csv":
        text = events_to_csv(session.events)
    elif fmt == "html":
        text = session_to_html(session)
    else:
        raise ValueError(f"unknown format: {fmt!r} (expected json|csv|html)")
    if out is not None:
        Path(out).write_text(text, encoding="utf-8")
    return text


__all__ = [
    "events_to_csv",
    "export_session",
    "session_to_dict",
    "session_to_html",
    "write_sidecar",
]
