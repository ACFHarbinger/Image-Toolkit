"""Crash bundle model.

A CrashBundle associates one telemetry session with the artifacts that make
up a post-mortem: the JVM hs_err log (if the JVM was loaded), optional gdb
output, and human/agent notes. It is a *view* over a Session plus paths -- it
does not copy the underlying files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .session import Session


@dataclass
class CrashBundle:
    """Post-mortem association for one session."""

    session: Session
    hs_err: Optional[Path] = None
    gdb_output: Optional[Path] = None
    notes: List[str] = field(default_factory=list)

    @property
    def crashed(self) -> bool:
        """Best-effort crash signal: truncated final telemetry line (process
        died mid-write) or orphaned spans (work in flight at the fault)."""
        return bool(self.session.truncated_final_line or self.session.orphaned_spans())

    def summarize(self) -> str:
        orphaned = len(self.session.orphaned_spans())
        return (
            f"pid={self.session.pid} events={len(self.session.events)} "
            f"truncated={self.session.truncated_final_line} orphaned={orphaned} "
            f"hs_err={'yes' if self.hs_err else 'no'}"
        )


__all__ = ["CrashBundle"]
