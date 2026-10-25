"""Report one stitch catalog route (#914).

``route`` stays a plain string in the contract: catalog ids contain dots and
hyphens, which are not Rust enum identifiers. This module does not read
images or start a stitch pipeline.
"""

from __future__ import annotations

from typing import Any

ROUTES = frozenset(
    {
        "stitch.stitch",
        "stitch.graph",
        "stitch.adjust",
        "stitch.canvas",
        "stitch.statistics",
        "stitch.sequence-builder",
        "stitch.hybrid",
        "stitch.animation-clusters",
    }
)

REASON = "stitch pipeline is not started"


def stitch_status(route: str) -> dict[str, Any]:
    if route not in ROUTES:
        raise ValueError("unknown stitch route")
    return {"route": route, "started": False, "reason": REASON}
