"""Process-local runtime coordination for native numerical workloads.

The current NumPy, SciPy, OpenCV, and PyMaxflow prototypes share native
libraries that have shown intermittent instability when invoked concurrently
inside a Qt process. Until heavy jobs move into isolated worker processes, the
engine serializes those calls behind this local lock.

Keeping the lock here makes the core package standalone. Applications may
schedule work however they choose, but the engine never imports a parent UI or
Image-Toolkit runtime service.
"""

from __future__ import annotations

from threading import RLock

NATIVE_COMPUTE_LOCK = RLock()

__all__ = ["NATIVE_COMPUTE_LOCK"]
