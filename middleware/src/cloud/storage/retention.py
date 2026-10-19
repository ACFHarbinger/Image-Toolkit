"""Retention of staged inputs, model caches and outputs; pure planning (#833).

Policies come from CloudSettings: inputs go after verified collection (plus
an optional TTL), caches by TTL and an LRU storage budget (never while a
running job references them), outputs after their retention window.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Sequence

from ..settings import CloudSettings

_DAY = 86400.0


class ObjectRole(str, Enum):
    INPUT = "input"
    CACHE = "cache"
    OUTPUT = "output"


@dataclass(frozen=True)
class StoredObject:
    key: str
    role: ObjectRole
    size_bytes: int
    last_used: float
    refcount: int = 0               # running jobs using it
    collected_at: float | None = None  # outputs/inputs: when collection was verified
    job_ended_at: float | None = None


@dataclass(frozen=True)
class Deletion:
    key: str
    reason: str


def plan_cleanup(objects: Sequence[StoredObject], settings: CloudSettings, now: float) -> List[Deletion]:
    out: List[Deletion] = []
    caches: List[StoredObject] = []
    for o in objects:
        if o.refcount > 0:
            continue
        if o.role is ObjectRole.INPUT:
            if o.collected_at is not None and now - o.collected_at >= settings.staged_input_ttl_days * _DAY:
                out.append(Deletion(o.key, "input no longer needed after verified collection"))
        elif o.role is ObjectRole.OUTPUT:
            anchor = o.collected_at if o.collected_at is not None else o.job_ended_at
            if anchor is not None and now - anchor >= settings.output_retention_days * _DAY:
                why = "collected output past retention" if o.collected_at else "uncollected output past retention"
                out.append(Deletion(o.key, why))
        else:
            caches.append(o)

    budget = settings.cache_budget_gb * 1024 ** 3
    keep: List[StoredObject] = []
    for c in sorted(caches, key=lambda c: c.last_used, reverse=True):
        if now - c.last_used >= settings.cache_ttl_days * _DAY:
            out.append(Deletion(c.key, "cache unused past TTL"))
        else:
            keep.append(c)
    used = sum(c.size_bytes for c in keep)
    for c in reversed(keep):  # least recently used first
        if used <= budget:
            break
        out.append(Deletion(c.key, "cache over storage budget"))
        used -= c.size_bytes
    return out
