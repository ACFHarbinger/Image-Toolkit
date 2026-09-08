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


_state_lock = threading.Lock()
_active_guards = 0
_restore_enabled = True


@contextmanager
def gc_disabled() -> Iterator[None]:
    """Run the enclosed block with the cyclic GC disabled.

    Process-level coordinator (R1.1, #556): overlapping guards nest by
    count — only the outermost entry disables, only the outermost exit
    restores the state captured at that entry. An inner guard exiting
    while an outer one is still active must NOT re-enable collection,
    or a worker thread could finalize GUI garbage off the GUI thread
    (the #478 crash class). Leaving an already-disabled collector
    disabled is preserved.
    """
    global _active_guards, _restore_enabled
    with _state_lock:
        if _active_guards == 0:
            _restore_enabled = gc.isenabled()
            gc.disable()
        _active_guards += 1
    try:
        yield
    finally:
        with _state_lock:
            _active_guards -= 1
            if _active_guards == 0 and _restore_enabled:
                gc.enable()


def gc_disabled_run(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator for worker ``run()`` methods: execute with the cyclic GC off."""

    @wraps(func)
    def _guarded(*args: Any, **kwargs: Any) -> Any:
        with gc_disabled():
            return func(*args, **kwargs)

    return _guarded
