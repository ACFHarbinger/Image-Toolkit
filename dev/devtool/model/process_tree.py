"""Process/thread tree model.

Derived from a Session's telemetry: the process id, its observed threads
(tid + name), and any child processes referenced by the event stream.
Pure derivation -- nothing is persisted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from debugtool import Session


@dataclass
class ProcessTree:
    """One process's observed threads and child pids."""

    pid: int
    threads: List[Tuple[int, str]] = field(default_factory=list)
    child_pids: List[int] = field(default_factory=list)

    @classmethod
    def from_session(cls, session: Session) -> "ProcessTree":
        threads: Set[Tuple[int, str]] = set()
        children: Set[int] = set()
        for e in session.events:
            if "tid" in e:
                threads.add((e["tid"], e.get("tname", "?")))
            # child processes surfaced via spawn/fork events
            child = e.get("child_pid") or e.get("spawn_pid")
            if child is not None:
                children.add(int(child))
        return cls(
            pid=session.pid,
            threads=sorted(threads),
            child_pids=sorted(children),
        )

    def thread_count(self) -> int:
        return len(self.threads)


__all__ = ["ProcessTree"]
