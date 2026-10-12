"""Off-thread parent/variant output fetch for the What Changed overlay (#754)."""
from __future__ import annotations

import os
import threading

from backend.src.constants import LOCAL_SOURCE_PATH
from backend.src.core.guidance_pair import PairLoadError, load_comparison_pair, persist_verdict
from PySide6.QtCore import QObject, Signal


def pair_cache_dir(directory: str | None = None) -> str:
    return directory or os.path.join(LOCAL_SOURCE_PATH, "Generated", "compare_pairs")


class _PairBus(QObject):
    loaded = Signal(object)
    failed = Signal(int, str)
    persisted = Signal()
    persist_failed = Signal(str)


class ComparisonPairLoader(QObject):
    """Fetch the provenance-bound pair off the UI thread."""

    loaded = Signal(object)
    failed = Signal(int, str)
    persisted = Signal()
    persist_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bus = _PairBus()
        self._bus.loaded.connect(self.loaded)
        self._bus.failed.connect(self.failed)
        self._bus.persisted.connect(self.persisted)
        self._bus.persist_failed.connect(self.persist_failed)
        self._persist_lock = threading.Lock()
        self._persist_revisions = {}

    def start(
        self,
        manager,
        *,
        parent_prompt_id: str,
        variant_prompt_id: str,
        generation: int,
        cache_dir: str | None = None,
        fetch=None,
    ) -> threading.Thread | None:
        getter = getattr(manager, "get_run", None)
        if not callable(getter):
            self._bus.failed.emit(generation, "missing run record")
            return
        fetch_fn = fetch
        if fetch_fn is None:
            fetch_fn = getattr(manager, "fetch_output", None)
        thread = threading.Thread(
            target=self._load,
            args=(
                getter,
                fetch_fn if callable(fetch_fn) else None,
                parent_prompt_id,
                variant_prompt_id,
                generation,
                pair_cache_dir(cache_dir),
            ),
            daemon=True,
            name="guidance-pair-load",
        )
        thread.start()
        return thread

    def persist(
        self,
        manager,
        traj,
        variant_prompt_id: str | None,
        persist_sidecar=None,
    ) -> threading.Thread:
        revision = self._persist_revisions.get(variant_prompt_id, 0) + 1
        self._persist_revisions[variant_prompt_id] = revision
        thread = threading.Thread(
            target=self._persist,
            args=(manager, traj, variant_prompt_id, persist_sidecar, revision),
            daemon=True,
            name="guidance-verdict-persist",
        )
        thread.start()
        return thread

    def _load(self, getter, fetch, parent_id, variant_id, generation, cache_dir) -> None:
        try:
            pair = load_comparison_pair(
                parent_record=getter(parent_id),
                variant_record=getter(variant_id),
                expected_parent=parent_id,
                expected_variant=variant_id,
                cache_dir=cache_dir,
                fetch=fetch,
                generation=generation,
            )
        except PairLoadError as exc:
            self._bus.failed.emit(generation, str(exc))
            return
        except Exception as exc:
            self._bus.failed.emit(generation, str(exc))
            return
        self._bus.loaded.emit(pair)

    def _persist(self, manager, traj, variant_prompt_id, persist_sidecar, revision=None) -> None:
        try:
            with self._persist_lock:
                if revision is not None and revision != self._persist_revisions.get(variant_prompt_id):
                    return
                persist_verdict(manager, traj, variant_prompt_id, persist_sidecar)
        except Exception as exc:
            self._bus.persist_failed.emit(str(exc))
            return
        self._bus.persisted.emit()
