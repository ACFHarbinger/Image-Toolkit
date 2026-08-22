"""Embedder warm-up, generic worker dispatch, and reap/error handling.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class _WorkerPlumbingMixin:
    """Warms the embedding model and manages the lifecycle of QThread workers."""

    def _warm_embedder(self) -> None:
        """Force the heavy embedding model to load on the MAIN thread once.

        torch / InsightFace lazily ``dlopen`` their native libraries on first
        use. Doing that first-time load inside a worker ``QThread`` while the
        JPype JVM is live triggers a heap-corruption crash ("corrupted size vs.
        prev_size", QSocketNotifier-from-another-thread) — the documented
        JVM + lazily-loaded-native-lib conflict. Warming here loads those libs
        on the main thread; subsequent worker-thread inference is then safe."""
        mode = self._config.embed_mode
        if mode in self._warmed_modes:
            return
        try:
            import numpy as np
            from backend.src.web.recon.embedder import embed

            embed(np.zeros((64, 64, 3), dtype=np.uint8), mode)
        except Exception as e:  # noqa: BLE001 - warm-up is best-effort
            logger.warning("Embedder warm-up failed for %s: %s", mode, e)
        finally:
            # Mark warmed regardless: a failed load won't succeed off-thread
            # either, and we must not retry it inside a worker.
            self._warmed_modes.add(mode)

    def _run_worker(self, worker, on_finished):
        # Workers are QThread subclasses (override run(), no event loop). A plain
        # QThread + moveToThread spins a glib socket-notifier event dispatcher in
        # the worker thread which SIGSEGVs under the live JVM.
        worker.status.connect(self._set_status)
        worker.sig_finished.connect(on_finished)
        worker.sig_finished.connect(lambda *_: self._reap_worker(worker))
        worker.error.connect(self._on_worker_error)
        worker.error.connect(lambda *_: self._reap_worker(worker))
        self._threads.append(worker)
        worker.start()

    def _reap_worker(self, worker):
        if worker in self._threads:
            self._threads.remove(worker)
        worker.wait()
        worker.deleteLater()

    def _on_worker_error(self, message: str):
        self._set_busy(False)
        self._set_status(f"Error: {message}")


__all__ = ["_WorkerPlumbingMixin"]
