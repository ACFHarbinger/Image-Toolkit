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
from gui.src.helpers.gc_safe import gc_disabled, gc_disabled_run


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


def test_nested_guards_restore_only_on_outermost_exit():
    # R1.1 (#556, CX-3): an inner guard exiting while the outer one is
    # still active must NOT re-enable collection.
    assert gc.isenabled(), "test precondition: GC starts enabled"
    with gc_disabled():
        assert gc.isenabled() is False
        with gc_disabled():
            assert gc.isenabled() is False
        assert gc.isenabled() is False, "inner exit re-enabled GC while outer active"
    assert gc.isenabled() is True


def test_nested_guards_restore_on_exception_in_inner():
    assert gc.isenabled(), "test precondition: GC starts enabled"
    with gc_disabled():
        with pytest.raises(RuntimeError), gc_disabled():
            raise RuntimeError("kaboom")
        assert gc.isenabled() is False
    assert gc.isenabled() is True


def test_overlapping_threads_keep_gc_disabled_until_last_exit():
    # The CX-3 interleaving: the outer guard exits while the inner one is
    # still active. Per-invocation snapshot/restore re-enables collection
    # under the live inner guard; the coordinator must not.
    import threading

    assert gc.isenabled(), "test precondition: GC starts enabled"
    outer_in = threading.Event()
    inner_in = threading.Event()
    release_outer = threading.Event()
    release_inner = threading.Event()
    observed = {}

    def outer():
        with gc_disabled():
            outer_in.set()
            assert release_outer.wait(timeout=10)

    def inner():
        assert outer_in.wait(timeout=10)
        with gc_disabled():
            inner_in.set()
            assert release_inner.wait(timeout=10)
            observed["inner_still_guarded"] = gc.isenabled() is False

    t1 = threading.Thread(target=outer)
    t1.start()
    t2 = threading.Thread(target=inner)
    t2.start()
    assert inner_in.wait(timeout=10)
    release_outer.set()  # outer exits while inner is still guarded
    t1.join(timeout=10)
    release_inner.set()
    t2.join(timeout=10)
    assert observed["inner_still_guarded"] is True, "outer exit re-enabled GC under live guard"
    assert gc.isenabled() is True


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


def test_base_qrunnable_worker_cancel_emits_finished_none_without_executing():
    executed = False
    finished: list[object] = []

    class _Task(BaseQRunnableWorker):
        def _execute(self) -> None:
            nonlocal executed
            executed = True

    task = _Task()
    task.signals.finished.connect(finished.append)
    task.cancel()
    task.run()

    assert executed is False
    assert finished == [None]
