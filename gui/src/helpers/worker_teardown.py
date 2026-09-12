"""Shared worker-teardown primitives (ui-arch-34/R1.1).

Every tab ``_lifecycle.py`` clone reimplemented the same teardown by hand —
``stop()``/``cancel()`` if present, ``requestInterruption()``, ``wait()``,
then closing its preview-window lists — with gratuitous local variation
(swallowed vs logged errors, joined vs fire-and-forget threads, windows
closed once vs twice). This module is the one shared teardown: tab
lifecycles keep their tab-specific halves (timers, daemons, gallery state)
and delegate the worker/window halves here.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def stop_worker(worker: Any, *, join: bool = True) -> None:
    """Idempotently stop one base worker (``None``-safe).

    Calls ``stop()`` (falling back to ``cancel()``), then
    ``requestInterruption()`` where available (``QThread`` only), then
    ``wait()`` where available and ``join`` is true (``QThread`` only —
    ``QRunnable``s have neither and return once ``stop()`` lands).
    Every step is exception-proof: teardown must never raise out of
    ``cancel_loading``/``closeEvent``.
    """
    if worker is None:
        return
    with contextlib.suppress(Exception):
        stop = getattr(worker, "stop", None) or getattr(worker, "cancel", None)
        if callable(stop):
            stop()
    with contextlib.suppress(Exception):
        interrupt = getattr(worker, "requestInterruption", None)
        if callable(interrupt):
            interrupt()
    if join:
        with contextlib.suppress(Exception):
            wait = getattr(worker, "wait", None)
            if callable(wait):
                wait()


def stop_workers(*workers: Any, join: bool = True) -> None:
    """Stop several workers (``None`` entries skipped)."""
    for worker in workers:
        stop_worker(worker, join=join)


def close_windows(host: Any, *attr_names: str) -> None:
    """Close + clear each named window-list attribute on ``host``.

    Missing attributes are skipped (tabs own different lists:
    ``open_preview_windows``, ``open_queue_windows``,
    ``open_image_preview_windows``). A window whose C++ object is already
    gone raises ``RuntimeError`` — routed to ``deleted_qobject_guard``
    (R0.6) instead of being silently swallowed.
    """
    from gui.src.qt_object_guard import deleted_qobject_guard

    for name in attr_names:
        wins = getattr(host, name, None)
        if not wins:
            continue
        for win in list(wins):
            try:
                win.close()
            except RuntimeError as exc:
                deleted_qobject_guard(exc, f"close_windows:{name}")
            except Exception:
                logger.debug("Suppressed Exception in close_windows", exc_info=True)
        with contextlib.suppress(Exception):
            wins.clear()


__all__ = ["close_windows", "stop_worker", "stop_workers"]
