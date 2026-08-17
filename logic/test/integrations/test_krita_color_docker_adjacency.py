"""Tests for CharacterColorsDocker._adjacent_region_names, which suggests
(never auto-applies) Propagate Correspondence targets by reading G1's
Regions group the same way the Line Art Segmentation Docker's Report
Region Adjacency action does.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REGION_GROUP_NAME = "Regions"
REGION_PREFIX = "Region — "


class _FakeNode:
    def __init__(self, name, alpha_mask, width, height):
        self._name = name
        self._alpha_mask = alpha_mask
        self._width = width
        self._height = height

    def name(self):
        return self._name

    def pixelData(self, x, y, width, height):
        pixels = bytearray(width * height * 4)
        for index, alpha in enumerate(self._alpha_mask):
            pixels[index * 4 + 3] = alpha
        return bytes(pixels)

    def childNodes(self):
        return []


class _FakeGroup:
    def __init__(self, name, children):
        self._name = name
        self._children = children

    def name(self):
        return self._name

    def childNodes(self):
        return self._children


class _FakeDocument:
    def __init__(self, width, height, root):
        self._width = width
        self._height = height
        self._root = root

    def width(self):
        return self._width

    def height(self):
        return self._height

    def rootNode(self):
        return self._root


def _mask_for(labels, label):
    return [255 if value == label else 0 for value in labels]


def _document_with_regions(labels, width, height, names_by_label):
    children = [
        _FakeNode(f"{REGION_PREFIX}{name}", _mask_for(labels, label), width, height)
        for label, name in names_by_label.items()
    ]
    group = _FakeGroup(REGION_GROUP_NAME, children)
    root = _FakeGroup("root", [group])
    return _FakeDocument(width, height, root)


def _load_color_docker(monkeypatch):
    krita_module = types.ModuleType("krita")

    class DockWidget:
        def canvasChanged(self, canvas):  # noqa: N802
            raise NotImplementedError

    class Krita:
        @staticmethod
        def instance():
            raise NotImplementedError

    krita_module.DockWidget = DockWidget
    krita_module.Krita = Krita

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

    class FakeQThread:
        def __init__(self, parent=None):
            self._parent = parent

        def start(self):
            self.run()

    qtcore = types.ModuleType("PyQt5.QtCore")
    qtcore.QByteArray = type("QByteArray", (), {})
    qtcore.QThread = FakeQThread
    qtcore.Signal = staticmethod(lambda _type: SignalDescriptor(_type))

    qtwidgets = types.ModuleType("PyQt5.QtWidgets")
    for name in (
        "QComboBox",
        "QFileDialog",
        "QInputDialog",
        "QLabel",
        "QLineEdit",
        "QPushButton",
        "QVBoxLayout",
        "QWidget",
    ):
        setattr(qtwidgets, name, type(name, (), {}))

    pyqt5 = types.ModuleType("PyQt5")
    pyqt5.QtCore = qtcore
    pyqt5.QtWidgets = qtwidgets

    monkeypatch.setitem(sys.modules, "krita", krita_module)
    monkeypatch.setitem(sys.modules, "PyQt5", pyqt5)
    monkeypatch.setitem(sys.modules, "PyQt5.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt5.QtWidgets", qtwidgets)

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
    return module.CharacterColorsDocker


def test_suggests_only_regions_touching_the_source(monkeypatch):
    docker = _load_color_docker(monkeypatch)
    width, height = 4, 4
    labels = [
        1, 1, 2, 2,
        1, 1, 2, 2,
        0, 0, 0, 0,
        3, 3, 0, 0,
    ]
    document = _document_with_regions(
        labels, width, height, {1: "region-a", 2: "region-b", 3: "region-c"}
    )
    assert docker._adjacent_region_names(document, "region-a") == ["region-b"]
    assert docker._adjacent_region_names(document, "region-c") == []


def test_returns_empty_without_a_regions_group(monkeypatch):
    docker = _load_color_docker(monkeypatch)
    document = _FakeDocument(2, 2, _FakeGroup("root", []))
    assert docker._adjacent_region_names(document, "region-a") == []


def test_returns_empty_for_unknown_source_region(monkeypatch):
    docker = _load_color_docker(monkeypatch)
    width, height = 2, 2
    labels = [1, 1, 1, 1]
    document = _document_with_regions(labels, width, height, {1: "region-a"})
    assert docker._adjacent_region_names(document, "region-missing") == []


def test_returns_empty_for_none_document(monkeypatch):
    docker = _load_color_docker(monkeypatch)
    assert docker._adjacent_region_names(None, "region-a") == []


def _regions_document():
    width, height = 4, 4
    labels = [
        1, 1, 2, 2,
        1, 1, 2, 2,
        0, 0, 0, 0,
        3, 3, 0, 0,
    ]
    return _document_with_regions(
        labels, width, height, {1: "region-a", 2: "region-b", 3: "region-c"}
    )


def test_suggests_the_material_of_a_uniquely_adjacent_assignment(monkeypatch):
    docker = _load_color_docker(monkeypatch)
    document = _regions_document()
    correspondence_set = {
        "correspondences": [{"id": "c1", "region_id": "region-b", "material_id": "hair"}]
    }
    index = docker._suggested_material_index(
        document, "region-a", correspondence_set, ["skin", "hair", "eyes"]
    )
    assert index == 1


def test_falls_back_to_index_zero_without_adjacency(monkeypatch):
    docker = _load_color_docker(monkeypatch)
    document = _regions_document()
    correspondence_set = {"correspondences": []}
    assert docker._suggested_material_index(
        document, "region-a", correspondence_set, ["skin", "hair"]
    ) == 0
    assert docker._suggested_material_index(
        document, "region-c", correspondence_set, ["skin", "hair"]
    ) == 0


def test_falls_back_to_index_zero_when_adjacent_materials_disagree(monkeypatch):
    docker = _load_color_docker(monkeypatch)
    width, height = 3, 3
    # region-b (3) sits between region-a (1) and region-c (2), touching both.
    labels = [
        1, 3, 2,
        1, 3, 2,
        1, 3, 2,
    ]
    document = _document_with_regions(
        labels, width, height, {1: "region-a", 2: "region-c", 3: "region-b"}
    )
    correspondence_set = {
        "correspondences": [
            {"id": "c1", "region_id": "region-a", "material_id": "skin"},
            {"id": "c2", "region_id": "region-c", "material_id": "hair"},
        ]
    }
    assert docker._suggested_material_index(
        document, "region-b", correspondence_set, ["skin", "hair", "eyes"]
    ) == 0


def test_ignores_suggested_material_not_in_bible(monkeypatch):
    docker = _load_color_docker(monkeypatch)
    document = _regions_document()
    correspondence_set = {
        "correspondences": [{"id": "c1", "region_id": "region-b", "material_id": "unknown"}]
    }
    assert docker._suggested_material_index(
        document, "region-a", correspondence_set, ["skin", "hair"]
    ) == 0


def test_adjacency_agreement_is_a_fraction_of_all_adjacent_regions(monkeypatch):
    docker = _load_color_docker(monkeypatch)
    width, height = 3, 3
    # region-b (3) touches region-a (1), region-c (2), and region-d (4).
    labels = [
        1, 3, 2,
        1, 3, 2,
        4, 3, 0,
    ]
    document = _document_with_regions(
        labels, width, height, {1: "region-a", 2: "region-c", 3: "region-b", 4: "region-d"}
    )
    correspondence_set = {
        "correspondences": [
            {"id": "c1", "region_id": "region-a", "material_id": "hair"},
            {"id": "c2", "region_id": "region-c", "material_id": "hair"},
            # region-d left unassigned -- only 2 of 3 adjacent regions vote.
        ]
    }
    agreement = docker._adjacency_agreement_by_material(document, "region-b", correspondence_set)
    assert agreement == {"hair": pytest.approx(2 / 3)}


def test_adjacency_agreement_is_empty_without_adjacency(monkeypatch):
    docker = _load_color_docker(monkeypatch)
    document = _regions_document()
    correspondence_set = {"correspondences": []}
    assert docker._adjacency_agreement_by_material(document, "region-c", correspondence_set) == {}


def test_adjacency_agreement_splits_across_disagreeing_materials(monkeypatch):
    docker = _load_color_docker(monkeypatch)
    width, height = 3, 3
    labels = [
        1, 3, 2,
        1, 3, 2,
        1, 3, 2,
    ]
    document = _document_with_regions(
        labels, width, height, {1: "region-a", 2: "region-c", 3: "region-b"}
    )
    correspondence_set = {
        "correspondences": [
            {"id": "c1", "region_id": "region-a", "material_id": "skin"},
            {"id": "c2", "region_id": "region-c", "material_id": "hair"},
        ]
    }
    agreement = docker._adjacency_agreement_by_material(document, "region-b", correspondence_set)
    assert agreement == {"skin": pytest.approx(0.5), "hair": pytest.approx(0.5)}
