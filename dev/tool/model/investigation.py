"""Durable Investigation model.

An Investigation is a portable, named folder under the workspace's
investigations directory. It holds append-only notes plus links to the
telemetry sessions (and later crash bundles) that back it. Persistence is a
JSON sidecar next to a JSONL notes log -- both plain, diffable, portable.

Lifecycle/retention/privacy of Investigations are human/CLI concerns
(see host.settings and the C4 MCP note about append-only mutation).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

META_FILENAME = "investigation.json"
MANIFEST_FILENAME = "manifest.json"
NOTES_FILENAME = "notes.jsonl"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Investigation:
    """One durable investigation folder."""

    name: str
    root: Path
    sessions: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    note_count: int = 0

    # ------------------------------------------------------------------
    # Creation / opening
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, name: str, parent: Path) -> "Investigation":
        """Create a new investigation folder (fails if it already exists)."""
        root = Path(parent) / name
        if root.exists():
            raise FileExistsError(f"investigation already exists: {root}")
        root.mkdir(parents=True)
        inv = cls(name=name, root=root)
        inv._write_meta()
        return inv

    @classmethod
    def open(cls, root: Path) -> "Investigation":
        """Open an existing investigation folder (must have a meta sidecar)."""
        root = Path(root)
        meta_path = root / META_FILENAME
        if not meta_path.exists():
            raise FileNotFoundError(f"no investigation at: {root}")
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return cls(
            name=data["name"],
            root=root,
            sessions=data.get("sessions", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            note_count=data.get("note_count", 0),
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @property
    def notes_path(self) -> Path:
        return self.root / NOTES_FILENAME

    @property
    def manifest(self) -> Dict[str, Any]:
        """Portable self-describing manifest (A5)."""
        return {
            "format": "tool.investigation",
            "version": 1,
            "name": self.name,
            "sessions": self.sessions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "note_count": self.note_count,
        }

    def _write_meta(self) -> None:
        self.updated_at = _utcnow_iso()
        payload = json.dumps(self.manifest, indent=2)
        (self.root / META_FILENAME).write_text(payload, encoding="utf-8")
        (self.root / MANIFEST_FILENAME).write_text(payload, encoding="utf-8")

    def append_note(self, text: str, author: str) -> Dict[str, Any]:
        """Append one attributed, timestamped note (append-only)."""
        note = {
            "t": _utcnow_iso(),
            "author": author,
            "text": text,
        }
        with open(self.notes_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(note) + "\n")
        self.note_count += 1
        self._write_meta()
        return note

    def notes(self) -> List[Dict[str, Any]]:
        """Return all notes in append order."""
        if not self.notes_path.exists():
            return []
        out = []
        for line in self.notes_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def link_session(self, session_path: str) -> None:
        """Record a telemetry session path backing this investigation."""
        if session_path not in self.sessions:
            self.sessions.append(session_path)
            self._write_meta()


__all__ = [
    "Investigation",
    "MANIFEST_FILENAME",
    "META_FILENAME",
    "NOTES_FILENAME",
]
