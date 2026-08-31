"""Regression: `_SyncBackupWorker.run()` must run with the cyclic GC disabled.

`json.loads` of the decrypted backup allocates enough to trip a collection on
the worker QThread; CPython's collector has no thread affinity, so a
collectable QWidget anywhere in the GUI's cyclic garbage would be finalized
off the GUI thread and segfault (the #461 crash class). See GH #478.
"""

from __future__ import annotations

import gc

import pytest

from gui.src.helpers.web.sync_backup_worker import _SyncBackupWorker


def test_run_disables_gc_during_task_and_restores_after():
    seen = {}

    def _fake_task():
        seen["enabled_during"] = gc.isenabled()

    assert gc.isenabled(), "test precondition: GC starts enabled"

    w = _SyncBackupWorker("sync", "Content", {"db": object(), "vault_manager": object()})
    w.run_sync = _fake_task  # type: ignore[method-assign]
    w.run()

    assert seen["enabled_during"] is False, "GC must be off while the task runs"
    assert gc.isenabled() is True, "GC must be restored after run()"
    assert w.params == {}, "handles must be dropped so QObject teardown is on the GUI thread"


def test_run_restores_gc_even_on_exception():
    def _boom():
        raise RuntimeError("kaboom")

    w = _SyncBackupWorker("backup", "Content", {"entries": []})
    w.run_backup = _boom  # type: ignore[method-assign]
    # sig_finished.emit on a bare QThread with no receiver is a no-op here.
    w.run()

    assert gc.isenabled() is True
    assert w.params == {}


def test_run_leaves_gc_disabled_if_it_was_already_disabled():
    gc.disable()
    try:
        w = _SyncBackupWorker("sync", "Content", {})
        w.run_sync = lambda: None  # type: ignore[method-assign]
        w.run()
        assert gc.isenabled() is False
    finally:
        gc.enable()
