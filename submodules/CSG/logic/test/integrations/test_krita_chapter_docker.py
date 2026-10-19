"""Tests for ChapterQueueDocker's path-resolution and worker-routing logic."""

import importlib.util
import sys
import types
from pathlib import Path


class FakeSignal:
    """Minimal stand-in for a Qt signal: connect stores callbacks, emit runs them."""

    def __init__(self):
        self._callbacks = []
        self.emitted = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        self.emitted.append(args)
        for callback in list(self._callbacks):
            callback(*args)


class FakeButton:
    def __init__(self, *args, **kwargs):
        self.clicked = FakeSignal()
        self._enabled = True
        self.enabled_calls = []

    def setEnabled(self, enabled):
        self._enabled = enabled
        self.enabled_calls.append(enabled)

    @property
    def enabled(self):
        return self._enabled


class FakeLabel:
    def __init__(self, *args, **kwargs):
        self.text = ""
        self.word_wrap = False

    def setText(self, text):
        self.text = text

    def setWordWrap(self, wrap):
        self.word_wrap = wrap


class FakeLayout:
    def __init__(self, *args, **kwargs):
        pass

    def addWidget(self, _widget):
        pass


class FakeDockWidget:
    def __init__(self, *args, **kwargs):
        self._title = ""
        self._widget = None

    def setWindowTitle(self, title):
        self._title = title

    def setWidget(self, widget):
        self._widget = widget

    def canvasChanged(self, canvas):  # noqa: N802
        raise NotImplementedError


class FakeKrita:
    instance_obj = None

    @classmethod
    def instance(cls):
        return cls.instance_obj


class FakeQThread:
    """Runs run() synchronously on start() so tests need no event loop."""

    def __init__(self, parent=None):
        self._parent = parent

    def start(self):
        self.run()


class SignalDescriptor:
    """Per-instance signal: Qt Signal() is a descriptor yielding one
    FakeSignal per instance, so two EngineWorkers never share callbacks."""

    def __init__(self, _type):
        self._store_key = object()

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        store = getattr(instance, "_fake_signals", None)
        if store is None:
            store = {}
            instance._fake_signals = store
        if self._store_key not in store:
            store[self._store_key] = FakeSignal()
        return store[self._store_key]

    def __set__(self, instance, value):
        store = getattr(instance, "_fake_signals", None)
        if store is None:
            store = {}
            instance._fake_signals = store
        store[self._store_key] = value


def _signal_factory(_type):
    return SignalDescriptor(_type)


def _load_chapter_docker(monkeypatch):
    krita_module = types.ModuleType("krita")
    krita_module.DockWidget = FakeDockWidget
    krita_module.Krita = FakeKrita

    qtwidgets = types.ModuleType("PyQt5.QtWidgets")
    qtwidgets.QFileDialog = types.SimpleNamespace(
        getExistingDirectory=staticmethod(lambda *a, **k: ""),
        getOpenFileName=staticmethod(lambda *a, **k: ("", "")),
    )
    qtwidgets.QInputDialog = types.SimpleNamespace(
        getText=staticmethod(lambda *a, **k: ("", False)),
        getInt=staticmethod(lambda *a, **k: (0, False)),
    )
    qtwidgets.QLabel = FakeLabel
    qtwidgets.QLineEdit = types.SimpleNamespace(Normal=0)
    qtwidgets.QPushButton = FakeButton
    qtwidgets.QVBoxLayout = FakeLayout
    class FakeQWidget:
        def __init__(self, *args, **kwargs):
            pass

    qtwidgets.QWidget = FakeQWidget

    qtcore = types.ModuleType("PyQt5.QtCore")
    qtcore.QThread = FakeQThread
    qtcore.Signal = _signal_factory

    pyqt5 = types.ModuleType("PyQt5")
    pyqt5.QtWidgets = qtwidgets
    pyqt5.QtCore = qtcore

    monkeypatch.setitem(sys.modules, "krita", krita_module)
    monkeypatch.setitem(sys.modules, "PyQt5", pyqt5)
    monkeypatch.setitem(sys.modules, "PyQt5.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "PyQt5.QtCore", qtcore)

    package_dir = (
        Path(__file__).parents[3] / "integrations/krita/pykrita/cel_shaded_generator"
    )
    package_name = "cel_shaded_generator"
    package = types.ModuleType(package_name)
    package.__path__ = [str(package_dir)]
    monkeypatch.setitem(sys.modules, package_name, package)

    module_name = f"{package_name}.chapter_docker"
    spec = importlib.util.spec_from_file_location(module_name, package_dir / "chapter_docker.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


class FakeEngineClient:
    """Records engine calls made by the docker."""

    def __init__(self):
        self.calls = []

    def add_chapter_page(self, request_id, directory, relative, panel_id):
        self.calls.append(("add_chapter_page", request_id, directory, relative, panel_id))

    def next_pending_chapter_page(self, request_id, directory):
        self.calls.append(("next_pending_chapter_page", request_id, directory))
        return {
            "page_id": "p1",
            "document_asset": "pages/01.kra",
            "panel_id": "panel-01",
        }

    def set_chapter_page_status(self, request_id, directory, page_id, status):
        self.calls.append(("set_chapter_page_status", request_id, directory, page_id, status))

    def project_progress_snapshot(self, request_id, directory):
        self.calls.append(("project_progress_snapshot", request_id, directory))
        return {
            "chapter": {
                "pages": [
                    {
                        "page_id": "p1",
                        "document_asset": "pages/01.kra",
                        "panel_id": "panel-01",
                        "status": "pending",
                    }
                ],
                "next_pending_page_id": "p1",
            }
        }


def test_relative_to_project_resolves_nested_paths(monkeypatch, tmp_path):
    docker = _load_chapter_docker(monkeypatch)
    project_dir = tmp_path / "project"
    pages_dir = project_dir / "pages"
    pages_dir.mkdir(parents=True)
    page = pages_dir / "01.kra"
    page.write_bytes(b"page")

    fake_self = types.SimpleNamespace(_project_directory=str(project_dir))
    assert docker.ChapterQueueDocker._relative_to_project(fake_self, str(page)) == "pages/01.kra"


def test_relative_to_project_rejects_paths_outside_the_project(monkeypatch, tmp_path):
    docker = _load_chapter_docker(monkeypatch)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    outside = tmp_path / "outside.kra"
    outside.write_bytes(b"page")

    fake_self = types.SimpleNamespace(_project_directory=str(project_dir))
    assert docker.ChapterQueueDocker._relative_to_project(fake_self, str(outside)) is None


def test_run_engine_disables_buttons_while_working(monkeypatch):
    module = _load_chapter_docker(monkeypatch)
    docker = module.ChapterQueueDocker()
    states = []

    def call():
        states.append([button.enabled for button in docker._buttons])
        return {"ok": True}

    module.EngineClient = lambda: FakeEngineClient()
    docker._run_worker(call, lambda _result: None, "err: ")
    assert states == [[False] * len(docker._buttons)]
    assert all(button.enabled for button in docker._buttons)


def test_run_engine_error_sets_status_with_prefix(monkeypatch):
    module = _load_chapter_docker(monkeypatch)
    docker = module.ChapterQueueDocker()

    def boom():
        raise RuntimeError("engine failed")

    docker._run_worker(boom, lambda _result: None, "Could not read: ")
    assert docker._status.text == "Could not read: engine failed"
    assert all(button.enabled for button in docker._buttons)


def test_add_page_runs_engine_off_thread_and_refreshes(monkeypatch, tmp_path):
    module = _load_chapter_docker(monkeypatch)
    docker = module.ChapterQueueDocker()
    project_dir = tmp_path / "project"
    pages_dir = project_dir / "pages"
    pages_dir.mkdir(parents=True)
    page = pages_dir / "01.kra"
    page.write_bytes(b"page")
    docker._project_directory = str(project_dir)

    module.QFileDialog.getOpenFileName = staticmethod(
        lambda *a, **k: (str(page), "Krita Documents (*.kra)")
    )
    module.QInputDialog.getText = staticmethod(lambda *a, **k: ("panel-01", True))

    client = FakeEngineClient()
    module.EngineClient = lambda: client

    docker._add_page()
    assert client.calls[0][0] == "add_chapter_page"
    assert client.calls[0][3] == "pages/01.kra"
    assert client.calls[0][4] == "panel-01"
    # Success handler refreshes the queue through a second worker run.
    assert client.calls[-1][0] == "project_progress_snapshot"
    assert docker._status.text == (
        "Chapter has 1 page(s), 0 accepted. "
        "Next pending: p1."
    )
    assert all(button.enabled for button in docker._buttons)


def test_open_next_pending_chains_document_open_and_status_update(monkeypatch, tmp_path):
    module = _load_chapter_docker(monkeypatch)
    docker = module.ChapterQueueDocker()
    project_dir = tmp_path / "project"
    pages_dir = project_dir / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "01.kra").write_bytes(b"page")
    docker._project_directory = str(project_dir)

    opened = []
    window = types.SimpleNamespace(addView=lambda document: opened.append(document))

    class FakeApplication:
        @staticmethod
        def activeWindow():
            return window

        @staticmethod
        def openDocument(path):
            return types.SimpleNamespace(fileName=lambda: path)

    module.Krita.instance_obj = FakeApplication()

    client = FakeEngineClient()
    module.EngineClient = lambda: client

    docker._open_next_pending()
    assert [call[0] for call in client.calls] == [
        "next_pending_chapter_page",
        "set_chapter_page_status",
    ]
    assert client.calls[1][3] == "p1"
    assert client.calls[1][4] == "in_progress"
    assert len(opened) == 1
    assert docker._status.text == "Opened pages/01.kra (panel panel-01)."
    assert all(button.enabled for button in docker._buttons)


def test_mark_active_page_status_matches_document_then_updates(monkeypatch, tmp_path):
    module = _load_chapter_docker(monkeypatch)
    docker = module.ChapterQueueDocker()
    project_dir = tmp_path / "project"
    pages_dir = project_dir / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "01.kra").write_bytes(b"page")
    docker._project_directory = str(project_dir)

    class FakeApplication:
        @staticmethod
        def activeDocument():
            return types.SimpleNamespace(fileName=lambda: str(pages_dir / "01.kra"))

    module.Krita.instance_obj = FakeApplication()

    client = FakeEngineClient()
    module.EngineClient = lambda: client

    docker._set_active_page_status("accepted")
    assert [call[0] for call in client.calls] == [
        "project_progress_snapshot",
        "set_chapter_page_status",
        "project_progress_snapshot",
    ]
    assert client.calls[1][3] == "p1"
    assert client.calls[1][4] == "accepted"
    # The status handler refreshes the queue afterwards.
    assert docker._status.text == (
        "Chapter has 1 page(s), 0 accepted. "
        "Next pending: p1."
    )
    assert all(button.enabled for button in docker._buttons)
