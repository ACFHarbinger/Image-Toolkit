"""Regression guard for a real live-discovered bug: Krita's PyKrita binding
requires every ``DockWidget`` subclass to override ``canvasChanged()``, or
instantiation raises ``NotImplementedError: DockWidget.canvasChanged() is
abstract and must be overridden``. This was missed for two new Dockers
(Character Colors, Line Art Segmentation) and only discovered live in Krita,
because nothing headless previously exercised the Docker modules themselves
(only their pure-Python host-neutral helper modules are unit tested). This
test imports each Docker module against a minimal stub ``krita``/``PyQt5``
so the missing-override class of bug is caught before it ships again.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_DOCKER_MODULES = [
    "color_docker.py",
    "segmentation_docker.py",
    "docker.py",
]


def _install_stub_krita_modules(monkeypatch):
    krita_module = types.ModuleType("krita")

    class DockWidget:
        def canvasChanged(self, canvas):  # noqa: N802
            raise NotImplementedError(
                "DockWidget.canvasChanged() is abstract and must be overridden"
            )

    class Krita:
        @staticmethod
        def instance():
            raise NotImplementedError("stub Krita.instance() is not used at import time")

    krita_module.DockWidget = DockWidget
    krita_module.Krita = Krita

    qtcore = types.ModuleType("PyQt5.QtCore")
    for name in ("QByteArray", "Qt"):
        setattr(qtcore, name, type(name, (), {}))
    qtcore.pyqtSignal = lambda *args, **kwargs: None

    qtgui = types.ModuleType("PyQt5.QtGui")
    for name in ("QColor", "QKeySequence", "QPainter", "QPen", "QPixmap"):
        setattr(qtgui, name, type(name, (), {}))

    qtwidgets = types.ModuleType("PyQt5.QtWidgets")
    for name in (
        "QCheckBox",
        "QComboBox",
        "QDialog",
        "QDialogButtonBox",
        "QFileDialog",
        "QFormLayout",
        "QInputDialog",
        "QLabel",
        "QLineEdit",
        "QMessageBox",
        "QPushButton",
        "QScrollArea",
        "QShortcut",
        "QSpinBox",
        "QVBoxLayout",
        "QWidget",
    ):
        setattr(qtwidgets, name, type(name, (), {}))

    pyqt5 = types.ModuleType("PyQt5")
    pyqt5.QtCore = qtcore
    pyqt5.QtGui = qtgui
    pyqt5.QtWidgets = qtwidgets

    monkeypatch.setitem(sys.modules, "krita", krita_module)
    monkeypatch.setitem(sys.modules, "PyQt5", pyqt5)
    monkeypatch.setitem(sys.modules, "PyQt5.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt5.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "PyQt5.QtWidgets", qtwidgets)
    return DockWidget


def _load(filename, monkeypatch):
    dock_widget = _install_stub_krita_modules(monkeypatch)
    package_dir = (
        Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator"
    )
    package_name = "cel_shaded_generator"
    package = types.ModuleType(package_name)
    package.__path__ = [str(package_dir)]
    monkeypatch.setitem(sys.modules, package_name, package)

    module_name = f"{package_name}.{Path(filename).stem}"
    spec = importlib.util.spec_from_file_location(module_name, package_dir / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module, dock_widget


@pytest.mark.parametrize("filename", _DOCKER_MODULES)
def test_docker_overrides_canvas_changed(filename, monkeypatch):
    module, dock_widget = _load(filename, monkeypatch)
    docker_classes = [
        value
        for value in vars(module).values()
        if isinstance(value, type) and issubclass(value, dock_widget) and value is not dock_widget
    ]
    assert docker_classes, f"{filename} defines no DockWidget subclass"
    for docker_class in docker_classes:
        assert "canvasChanged" in docker_class.__dict__, (
            f"{docker_class.__name__} does not override canvasChanged(); Krita's "
            "DockWidget requires every subclass to override it"
        )
