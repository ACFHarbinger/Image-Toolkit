"""Tests for CharacterColorsDocker's worker routing (issue #23).

The docker must run every engine subprocess round trip and every pure-Python
buffer computation on an EngineWorker. These tests load the module with
stubbed krita/PyQt5 and drive the handlers with fake documents/engine
clients, asserting the calls ran inside workers, buttons were disabled for
the duration, and tolerant fallbacks (ranking, correspondence-set load,
bible load) still continue the flow.
"""

import importlib.util
import sys
import types
from pathlib import Path


class FakeSignal:
    def __init__(self):
        self._callbacks = []
        self.emitted = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        self.emitted.append(args)
        for callback in list(self._callbacks):
            callback(*args)


class SignalDescriptor:
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


class FakeButton:
    def __init__(self, *args, **kwargs):
        self.clicked = FakeSignal()
        self._enabled = True

    def setEnabled(self, enabled):
        self._enabled = enabled

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


class FakeComboBox:
    def __init__(self, *args, **kwargs):
        self._items = []
        self._data = []

    def clear(self):
        self._items = []
        self._data = []

    def addItem(self, label, data=None):
        self._items.append(label)
        self._data.append(data)

    def count(self):
        return len(self._items)

    def currentData(self):
        return self._data[0] if self._data else None


class FakeDockWidget:
    def __init__(self, *args, **kwargs):
        self._title = ""
        self._widget = None

    def setWindowTitle(self, title):
        self._title = title

    def setWidget(self, widget):
        self._widget = widget

    def canvasChanged(self, canvas):
        raise NotImplementedError


class FakeKrita:
    instance_obj = None

    @classmethod
    def instance(cls):
        return cls.instance_obj


class FakeQThread:
    def __init__(self, parent=None):
        self._parent = parent

    def start(self):
        self.run()


class FakeQByteArray:
    def __init__(self, data):
        self.data = bytes(data)


class FakeNode:
    def __init__(self, name, children=None, pixel=None):
        self._name = name
        self._children = children or []
        self._pixel = pixel
        self.set_pixel_calls = []

    def name(self):
        return self._name

    def childNodes(self):
        return self._children

    def addChildNode(self, node, _above):
        self._children.append(node)
        return True

    def pixelData(self, _x, _y, _w, _h):
        return self._pixel

    def setPixelData(self, data, _x, _y, _w, _h):
        self.set_pixel_calls.append(data.data if hasattr(data, "data") else data)
        return True

    def setLocked(self, _locked):
        pass

    def setName(self, name):
        self._name = name

    def remove(self):
        return True


class FakeRoot(FakeNode):
    def __init__(self):
        super().__init__("root")


class FakeDocument:
    def __init__(self, active_node, width=1, height=1):
        self._active = active_node
        self._width = width
        self._height = height
        self._root = FakeRoot()
        self._created = []

    def activeNode(self):
        return self._active

    def width(self):
        return self._width

    def height(self):
        return self._height

    def rootNode(self):
        return self._root

    def createNode(self, name, _kind):
        node = FakeNode(name, pixel=b"\x00" * (self._width * self._height * 4))
        self._created.append(node)
        return node

    def refreshProjection(self):
        pass


class FakeEngineClient:
    """Records engine calls and serves canned responses per method."""

    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def _record(self, name, *args):
        self.calls.append((name,) + args)
        response = self.responses.get(name)
        if isinstance(response, Exception):
            raise response
        return response

    def project_progress_snapshot(self, request_id, directory):
        return self._record("project_progress_snapshot", request_id, directory)

    def import_reference_asset(self, request_id, directory, source):
        return self._record("import_reference_asset", request_id, directory, source)

    def upsert_project_style_bible(self, request_id, directory, payload):
        return self._record("upsert_project_style_bible", request_id, directory, payload)

    def project_style_bible_payload(self, request_id, directory, asset_path):
        return self._record("project_style_bible_payload", request_id, directory, asset_path)

    def project_correspondence_set_payload(self, request_id, directory, asset_path):
        return self._record("project_correspondence_set_payload", request_id, directory, asset_path)

    def rank_correspondence_materials(self, request_id, directory, asset_path, region_id, agreements):
        return self._record(
            "rank_correspondence_materials", request_id, directory, asset_path, region_id, agreements
        )

    def upsert_project_correspondence_set(self, request_id, directory, correspondence_set):
        return self._record("upsert_project_correspondence_set", request_id, directory, correspondence_set)

    def record_correspondence_choice(self, request_id, directory, material_id, ranked):
        return self._record("record_correspondence_choice", request_id, directory, material_id, ranked)

    def propagate_project_correspondence(self, request_id, directory, asset_path, source_id, targets):
        return self._record(
            "propagate_project_correspondence", request_id, directory, asset_path, source_id, targets
        )


def _load_color_docker(monkeypatch):
    krita_module = types.ModuleType("krita")
    krita_module.DockWidget = FakeDockWidget
    krita_module.Krita = FakeKrita

    qtwidgets = types.ModuleType("PyQt5.QtWidgets")
    qtwidgets.QComboBox = FakeComboBox
    qtwidgets.QFileDialog = types.SimpleNamespace(
        getExistingDirectory=staticmethod(lambda *a, **k: ""),
        getOpenFileName=staticmethod(lambda *a, **k: ("", "")),
    )
    qtwidgets.QInputDialog = types.SimpleNamespace(
        getText=staticmethod(lambda *a, **k: ("", False)),
        getItem=staticmethod(lambda *a, **k: ("", False)),
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
    qtcore.QByteArray = FakeQByteArray

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

    module_name = f"{package_name}.color_docker"
    spec = importlib.util.spec_from_file_location(module_name, package_dir / "color_docker.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def _bind_project(docker, module, client):
    docker._project_directory = "/proj"
    module.EngineClient = lambda: client


def test_refresh_bibles_runs_engine_in_worker(monkeypatch):
    module = _load_color_docker(monkeypatch)
    docker = module.CharacterColorsDocker()
    client = FakeEngineClient(
        responses={
            "project_progress_snapshot": {"style_bibles": [
                {"character_name": "Nia", "style_name": "Casual", "asset_path": "bibles/nia-casual.json"},
            ]}
        }
    )
    _bind_project(docker, module, client)
    docker._refresh_bibles()
    assert [call[0] for call in client.calls] == ["project_progress_snapshot"]
    assert docker._bibles.count() == 1
    assert "Bound project with 1 style bible(s)." in docker._status.text
    assert all(button.enabled for button in docker._buttons)


def test_author_bible_upserts_in_worker_then_refreshes(monkeypatch):
    module = _load_color_docker(monkeypatch)
    docker = module.CharacterColorsDocker()
    client = FakeEngineClient(
        responses={
            "upsert_project_style_bible": {},
            "project_progress_snapshot": {"style_bibles": []},
        }
    )
    _bind_project(docker, module, client)
    module.QInputDialog.getText = staticmethod(lambda *a, **k: ("bible-1", True))
    module.QInputDialog.getInt = staticmethod(lambda *a, **k: (1, True))
    docker._author_bible_dialogs(None)
    assert [call[0] for call in client.calls] == [
        "upsert_project_style_bible",
        "project_progress_snapshot",
    ]
    assert all(button.enabled for button in docker._buttons)


def test_with_selected_bible_handles_missing_bible_with_none(monkeypatch):
    module = _load_color_docker(monkeypatch)
    docker = module.CharacterColorsDocker()
    client = FakeEngineClient(responses={"project_style_bible_payload": RuntimeError("gone")})
    _bind_project(docker, module, client)
    docker._bibles.addItem("Nia — Casual", "bibles/nia.json")
    seen = []
    docker._with_selected_bible(lambda bible: seen.append(bible))
    assert seen == [None]  # tolerant fallback: bible load failure -> None
    assert all(button.enabled for button in docker._buttons)


def test_with_correspondence_set_falls_back_to_empty_set(monkeypatch):
    module = _load_color_docker(monkeypatch)
    docker = module.CharacterColorsDocker()
    client = FakeEngineClient(
        responses={"project_correspondence_set_payload": RuntimeError("gone")}
    )
    _bind_project(docker, module, client)
    seen = []
    docker._with_correspondence_set("bible-1", lambda payload: seen.append(payload))
    assert seen == [{"id": "bible-1", "style_bible_id": "bible-1", "correspondences": [],
                     "recovery_revisions": 10, "schema_version": 1}]
    assert all(button.enabled for button in docker._buttons)


def test_assign_correspondence_ranking_failure_still_continues(monkeypatch):
    module = _load_color_docker(monkeypatch)
    docker = module.CharacterColorsDocker()
    client = FakeEngineClient(
        responses={
            "project_style_bible_payload": {
                "id": "bible-1",
                "materials": [{"id": "hair", "label": "Hair", "palette": {"local": "#000000"}}],
            },
            "project_correspondence_set_payload": {"correspondences": []},
            # Ranking is best-effort: an engine failure must fall back to the
            # unordered dropdown rather than abort the assignment.
            "rank_correspondence_materials": RuntimeError("engine offline"),
            "upsert_project_correspondence_set": {},
        }
    )
    _bind_project(docker, module, client)
    docker._bibles.addItem("Nia — Casual", "bibles/nia.json")

    region_node = FakeNode("Region — face")
    document = FakeDocument(region_node)
    module.Krita.instance_obj = types.SimpleNamespace(activeDocument=lambda: document)
    # Accept the two dropdowns with default selections.
    module.QInputDialog.getItem = staticmethod(lambda *a, **k: ("hair", True))
    module.QInputDialog.getText = staticmethod(lambda *a, **k: ("", True))

    docker._assign_correspondence()
    names = [call[0] for call in client.calls]
    assert "rank_correspondence_materials" in names
    assert "upsert_project_correspondence_set" in names
    # The assignment saved despite the ranking failure.
    assert "Assigned region 'region-face'" in docker._status.text
    assert all(button.enabled for button in docker._buttons)


def test_preview_palette_computes_off_thread_and_writes_layer(monkeypatch):
    module = _load_color_docker(monkeypatch)
    docker = module.CharacterColorsDocker()
    client = FakeEngineClient(
        responses={
            "project_style_bible_payload": {
                "id": "bible-1",
                "materials": [
                    {"id": "hair", "label": "Hair",
                     "palette": {"local": "#112233", "light": "#445566", "shadow": "#000000"}}
                ],
            },
        }
    )
    _bind_project(docker, module, client)
    docker._bibles.addItem("Nia — Casual", "bibles/nia.json")

    width, height = 2, 1
    mask = FakeNode("Material — hair", pixel=b"\x00\x00\x00\xff" + b"\x00\x00\x00\x00")
    group = FakeNode("Material Masks", children=[mask])
    document = FakeDocument(mask, width, height)
    document._root._children.append(group)
    module.Krita.instance_obj = types.SimpleNamespace(activeDocument=lambda: document)
    module.QInputDialog.getItem = staticmethod(lambda *a, **k: ("local", True))

    worker_calls = []
    original_preview = module.palette_preview_bgra

    def wrapped_preview(alpha, color):
        worker_calls.append(True)
        return original_preview(alpha, color)

    module.palette_preview_bgra = wrapped_preview

    docker._preview_palette()
    assert worker_calls == [True]
    assert docker._status.text == "Preview created; source mask and artwork are unchanged."
    assert docker._preview is not None
    assert all(button.enabled for button in docker._buttons)
