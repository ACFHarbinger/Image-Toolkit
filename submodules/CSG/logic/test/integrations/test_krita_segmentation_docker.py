"""Tests for SegmentationDocker's worker routing (issue #23).

The docker must run the pure-Python per-pixel buffer computations off the UI
thread while keeping every Krita document/node API call on it. These tests
load the module with stubbed krita/PyQt5 (matching the other integration
tests) and drive the handlers with fake documents, asserting the compute ran
inside the worker and the result was applied back on the calling thread.
"""

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
    """Runs run() synchronously on start() so tests need no event loop."""

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

    def remove(self):
        pass


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


def _load_segmentation_docker(monkeypatch):
    krita_module = types.ModuleType("krita")
    krita_module.DockWidget = FakeDockWidget
    krita_module.Krita = FakeKrita

    qtwidgets = types.ModuleType("PyQt5.QtWidgets")
    qtwidgets.QInputDialog = types.SimpleNamespace(
        getInt=staticmethod(lambda *a, **k: (4, True)),
    )
    qtwidgets.QLabel = FakeLabel
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

    module_name = f"{package_name}.segmentation_docker"
    spec = importlib.util.spec_from_file_location(module_name, package_dir / "segmentation_docker.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def _ink_buffer(width, height, ink_indexes):
    return bytes(1 if index in ink_indexes else 0 for index in range(width * height))


def test_close_gaps_computes_off_thread_and_writes_layer(monkeypatch):
    module = _load_segmentation_docker(monkeypatch)
    docker = module.SegmentationDocker()

    width, height = 3, 3
    # Ink ring around the center pixel; gap radius 1.
    ink = _ink_buffer(width, height, {0, 1, 2, 3, 5, 6, 7, 8})
    node = FakeNode("line-art", pixel=b"".join(
        b"\x00\x00\x00\xff" if value else b"\x00\x00\x00\x00" for value in ink
    ))
    document = FakeDocument(node, width, height)
    module.Krita.instance_obj = types.SimpleNamespace(activeDocument=lambda: document)
    module.QInputDialog.getInt = staticmethod(lambda *a, **k: (1, True))

    called_in_worker = []
    original_close = module.close_line_gaps_bytes

    def wrapped_close(ink_bytes, w, h, gap):
        called_in_worker.append(True)
        return original_close(ink_bytes, w, h, gap)

    module.close_line_gaps_bytes = wrapped_close

    docker._close_gaps()
    assert called_in_worker == [True]
    # The worker ran synchronously under the stub; the result was written back.
    assert len(document._created) == 2  # Line Art group + gap-closed layer
    closed_layer = document._created[1]
    assert closed_layer.set_pixel_calls, "result must be written back via setPixelData"
    assert docker._status.text.startswith("Created 'Line Art — Gap Closed")
    assert all(button.enabled for button in docker._buttons)


def test_segment_regions_chains_compute_and_writes_layers(monkeypatch):
    module = _load_segmentation_docker(monkeypatch)
    docker = module.SegmentationDocker()

    width, height = 3, 3
    # Ink ring around center: exactly one enclosed background region.
    ink = _ink_buffer(width, height, {0, 1, 2, 3, 5, 6, 7, 8})
    node = FakeNode("line-art", pixel=b"".join(
        b"\x00\x00\x00\xff" if value else b"\x00\x00\x00\x00" for value in ink
    ))
    document = FakeDocument(node, width, height)
    module.Krita.instance_obj = types.SimpleNamespace(activeDocument=lambda: document)
    # Keep every region: minimum area 1.
    module.QInputDialog.getInt = staticmethod(lambda *a, **k: (1, True))

    worker_calls = []
    original_segment = module.segment_regions_bytes
    original_filter = module.filter_small_regions

    def wrapped_segment(ink_bytes, w, h):
        worker_calls.append("segment")
        return original_segment(ink_bytes, w, h)

    def wrapped_filter(labels, min_area):
        worker_calls.append("filter")
        return original_filter(labels, min_area)

    module.segment_regions_bytes = wrapped_segment
    module.filter_small_regions = wrapped_filter

    docker._segment_regions()
    assert worker_calls == ["segment", "filter"]
    # Regions group + one region layer.
    region_layers = [node for node in document._created if node.name().startswith("Region — ")]
    assert len(region_layers) == 1
    assert region_layers[0].set_pixel_calls
    assert "Created 1 region layer(s)" in docker._status.text
    assert all(button.enabled for button in docker._buttons)


def test_report_adjacency_computes_off_thread(monkeypatch):
    module = _load_segmentation_docker(monkeypatch)
    docker = module.SegmentationDocker()

    width, height = 2, 1
    # Two adjacent region layers, each one pixel.
    region_a = FakeNode(
        "Region — A", pixel=b"\x00\x00\x00\xff" + b"\x00\x00\x00\x00"
    )
    region_b = FakeNode(
        "Region — B", pixel=b"\x00\x00\x00\x00" + b"\x00\x00\x00\xff"
    )
    group = FakeNode("Regions", children=[region_a, region_b])
    document = FakeDocument(None, width, height)
    document._root._children.append(group)
    module.Krita.instance_obj = types.SimpleNamespace(activeDocument=lambda: document)

    worker_calls = []
    original_adjacency = module.region_adjacency_bytes

    def wrapped_adjacency(labels, w, h):
        worker_calls.append(True)
        return original_adjacency(labels, w, h)

    module.region_adjacency_bytes = wrapped_adjacency

    docker._report_adjacency()
    assert worker_calls == [True]
    assert "1 adjacent region pair(s): A—B" in docker._status.text
    assert all(button.enabled for button in docker._buttons)
