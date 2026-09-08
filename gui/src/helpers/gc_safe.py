"""Reusable cyclic-GC guard for GUI worker threads (the #478 crash class).

CPython's cyclic collector is process-global and has no thread affinity: any
thread whose allocations trip the collection threshold may run a collection,
and a collectable ``QWidget`` sitting in the GUI's cyclic garbage is then
finalized *on that thread* — ``QWidget::~QWidget`` off the GUI thread
segfaults (the #461 crash class). Workers that parse large JSON payloads,
walk big listings, or otherwise allocate heavily trip the threshold
regularly, so they must run with the cyclic GC disabled. Refcounted frees
are unaffected; the GUI thread's next allocation re-collects once the guard
restores the GC.

Usage
-----
- Subclasses of :class:`gui.src.helpers.base.BaseQThreadWorker` /
  :class:`gui.src.helpers.base.BaseQRunnableWorker` are already guarded —
  implement ``_execute()`` and you are covered.
- Workers overriding ``run()`` directly: decorate it with
  ``@gc_disabled_run``. Works identically for ``QThread.run()``,
  ``QRunnable.run()`` (QThreadPool threads), and plain
  ``threading.Thread`` targets.
- New workers must subclass :class:`gui.src.helpers.base.BaseQThreadWorker`
  / :class:`gui.src.helpers.base.BaseQRunnableWorker` (R1.1, #556) — raw
  ``QThread``/``QRunnable`` subclasses in ``helpers/`` fail CI
  (``backend/validation/check_worker_base.py``).
"""

from __future__ import annotations

import gc
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Any

__all__ = ["gc_disabled", "gc_disabled_run"]

_gc_lock = threading.Lock()
_gc_disabled_count = 0
_initial_gc_enabled = True


@contextmanager
def gc_disabled() -> Iterator[None]:
    """Run the enclosed block with the cyclic GC disabled.

    Thread-safe refcounted: ensures that when multiple worker threads run
    concurrently, one thread finishing does not prematurely re-enable GC
    while other worker threads are still executing.
    """
    global _gc_disabled_count, _initial_gc_enabled
    with _gc_lock:
        if _gc_disabled_count == 0:
            _initial_gc_enabled = gc.isenabled()
            gc.disable()
        _gc_disabled_count += 1
    try:
        yield
    finally:
        with _gc_lock:
            _gc_disabled_count -= 1
            if _gc_disabled_count == 0 and _initial_gc_enabled:
                gc.enable()


def gc_disabled_run(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator for worker ``run()`` methods: execute with the cyclic GC off."""

    @wraps(func)
    def _guarded(*args: Any, **kwargs: Any) -> Any:
        with gc_disabled():
            return func(*args, **kwargs)

    return _guarded
