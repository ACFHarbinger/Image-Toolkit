"""#480: the reusable cyclic-GC guard for GUI worker threads.

CPython's collector is process-global with no thread affinity; any worker
thread whose allocations trip it can finalize a collectable QWidget from
the GUI's cyclic garbage off the GUI thread (#478 / #461 crash class). The
guard must disable the cyclic GC for the whole ``run()`` and restore the
prior state afterwards — exception or not, and without enabling it if it
was already off.
"""

from __future__ import annotations

import gc

import pytest
from gui.src.helpers.base import BaseQRunnableWorker, BaseQThreadWorker
from gui.src.helpers.gc_safe import GcSafeThread, gc_disabled, gc_disabled_run


def test_context_manager_disables_and_restores():
    assert gc.isenabled(), "test precondition: GC starts enabled"
    with gc_disabled():
        assert gc.isenabled() is False
    assert gc.isenabled() is True


def test_context_manager_restores_on_exception():
    with pytest.raises(RuntimeError), gc_disabled():
        raise RuntimeError("kaboom")
    assert gc.isenabled() is True


def test_context_manager_leaves_disabled_if_already_disabled():
    gc.disable()
    try:
        with gc_disabled():
            assert gc.isenabled() is False
        assert gc.isenabled() is False
    finally:
        gc.enable()


class _Plain:
    @gc_disabled_run
    def work(self, value):
        return value, gc.isenabled()


def test_decorator_guards_plain_method_and_keeps_return_value():
    value, enabled_during = _Plain().work(42)
    assert value == 42
    assert enabled_during is False
    assert gc.isenabled() is True


def test_decorator_restores_on_exception():
    class _Boom:
        @gc_disabled_run
        def work(self):
            raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError):
        _Boom().work()
    assert gc.isenabled() is True


def test_decorator_leaves_disabled_if_already_disabled():
    gc.disable()
    try:

        class _Noop:
            @gc_disabled_run
            def work(self):
                pass

        _Noop().work()
        assert gc.isenabled() is False
    finally:
        gc.enable()


def test_gc_safe_thread_runs_execute_with_gc_disabled():
    seen = {}

    class _Worker(GcSafeThread):
        def _execute(self) -> None:
            seen["enabled_during"] = gc.isenabled()

    assert gc.isenabled(), "test precondition: GC starts enabled"
    # run() directly, on the test thread — same as the #478 regression test.
    _Worker().run()
    assert seen["enabled_during"] is False
    assert gc.isenabled() is True


def test_base_qthread_worker_guards_execute():
    seen = {}

    class _Worker(BaseQThreadWorker):
        def _execute(self) -> None:
            seen["enabled_during"] = gc.isenabled()

    assert gc.isenabled(), "test precondition: GC starts enabled"
    # error/finished emissions on a bare QThread with no receiver are no-ops.
    _Worker().run()
    assert seen["enabled_during"] is False
    assert gc.isenabled() is True


def test_base_qthread_worker_restores_gc_when_execute_raises():
    class _Worker(BaseQThreadWorker):
        def _execute(self) -> None:
            raise RuntimeError("kaboom")

    _Worker().run()  # exception routes to the error signal, not the caller
    assert gc.isenabled() is True


def test_base_qrunnable_worker_guards_execute():
    seen = {}

    class _Task(BaseQRunnableWorker):
        def _execute(self) -> None:
            seen["enabled_during"] = gc.isenabled()

    assert gc.isenabled(), "test precondition: GC starts enabled"
    _Task().run()
    assert seen["enabled_during"] is False
    assert gc.isenabled() is True


def test_base_qrunnable_worker_restores_gc_when_execute_raises():
    class _Task(BaseQRunnableWorker):
        def _execute(self) -> None:
            raise RuntimeError("kaboom")

    _Task().run()  # exception routes to the signals.error, not the caller
    assert gc.isenabled() is True
