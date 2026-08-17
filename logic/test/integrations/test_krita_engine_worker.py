"""Tests for EngineWorker (issue #23: off-UI-thread Docker engine calls).

The worker is a thin QThread subclass; its run() logic is the interesting,
testable part, so these tests load the module with a stubbed PyQt5 (matching
the other integration tests) and drive run() directly, capturing the emitted
signals synchronously via fake signal objects.
"""

import importlib.util
import sys
import types
from pathlib import Path


class FakeSignal:
    def __init__(self):
        self.emitted = []

    def emit(self, *args):
        self.emitted.append(args)

    def connect(self, _callback):
        pass


def _make_pyqt5_qthread():
    """A stub PyQt5.QtCore.QThread whose run() is invoked directly by tests.

    Real QThread needs an event loop to deliver signals; for the worker's
    deterministic run() body we only need the class + Signal factory.
    """
    def signal_factory(_type):
        return FakeSignal()

    qthread = types.SimpleNamespace(Signal=staticmethod(signal_factory))

    class QThreadStub:
        def __init__(self, parent=None):
            self._parent = parent

        def start(self):
            self.run()

    qthread.QThread = QThreadStub
    return qthread


def _load_worker(monkeypatch):
    pyqt5_core = _make_pyqt5_qthread()
    pyqt5 = types.ModuleType("PyQt5")
    pyqt5.QtCore = pyqt5_core
    monkeypatch.setitem(sys.modules, "PyQt5", pyqt5)
    monkeypatch.setitem(sys.modules, "PyQt5.QtCore", pyqt5_core)

    path = (
        Path(__file__).parents[3]
        / "integrations/krita/pykrita/cel_shaded_generator/engine_worker.py"
    )
    spec = importlib.util.spec_from_file_location("krita_engine_worker", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_emits_result_on_success(monkeypatch):
    module = _load_worker(monkeypatch)
    worker = module.EngineWorker(lambda: {"ok": True})
    worker.start()
    assert worker.finished_ok.emitted == [({"ok": True},)]
    assert worker.error.emitted == []
    assert worker.busy_changed.emitted == [(True,), (False,)]


def test_worker_emits_error_on_failure(monkeypatch):
    module = _load_worker(monkeypatch)

    def boom():
        raise RuntimeError("engine failed")

    worker = module.EngineWorker(boom)
    worker.start()
    assert worker.finished_ok.emitted == []
    assert worker.error.emitted == [("engine failed",)]
    assert worker.busy_changed.emitted == [(True,), (False,)]


def test_worker_reports_any_exception_type_as_message(monkeypatch):
    module = _load_worker(monkeypatch)
    worker = module.EngineWorker(lambda: (_ for _ in ()).throw(ValueError("bad payload")))
    worker.start()
    assert worker.error.emitted == [("bad payload",)]
