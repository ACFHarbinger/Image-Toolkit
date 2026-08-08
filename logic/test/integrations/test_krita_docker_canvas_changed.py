"""Regression guard for a real live-discovered bug: Krita's PyKrita binding
requires every ``DockWidget`` subclass to override ``canvasChanged()``, or
instantiation raises ``NotImplementedError: DockWidget.canvasChanged() is
abstract and must be overridden``. This was missed for two new Dockers
(Character Colors, Line Art Segmentation) and only discovered live in Krita,
because nothing headless previously exercised the Docker modules themselves
(only their pure-Python host-neutral helper modules are unit tested). This
test imports each Docker module against a minimal stub ``krita``/``PyQt5``
so the missing-override class of bug is caught before it ships again.

It also imports the plugin's ``__init__.py`` entry point itself -- the exact
path Krita's plugin loader takes -- against the same stub, so an import-time
failure there (a bad sibling import, a typo in a registered class name) is
caught headlessly too, complementing the per-class ``canvasChanged`` check
above (which catches instantiation-time failures instead).
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
    "chapter_docker.py",
]


class _StubKritaInstance:
    def __init__(self):
        self.registered_factories = []

    def addDockWidgetFactory(self, factory):  # noqa: N802
        self.registered_factories.append(factory)


def _install_stub_krita_modules(monkeypatch):
    krita_module = types.ModuleType("krita")

    class DockWidget:
        def canvasChanged(self, canvas):  # noqa: N802
            raise NotImplementedError(
                "DockWidget.canvasChanged() is abstract and must be overridden"
            )

    class DockWidgetFactory:
        def __init__(self, factory_id, dock_position, docker_class):
            self.factory_id = factory_id
            self.dock_position = dock_position
            self.docker_class = docker_class

    class DockWidgetFactoryBase:
        DockRight = "DockRight"

    krita_instance = _StubKritaInstance()

    class Krita:
        @staticmethod
        def instance():
            return krita_instance

    krita_module.DockWidget = DockWidget
    krita_module.DockWidgetFactory = DockWidgetFactory
    krita_module.DockWidgetFactoryBase = DockWidgetFactoryBase
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
    return DockWidget, krita_instance


def _package_dir():
    return Path(__file__).parents[3] / "integrations/krita/pykrita/cel_shaded_generator"


def _load(filename, monkeypatch):
    dock_widget, krita_instance = _install_stub_krita_modules(monkeypatch)
    package_dir = _package_dir()
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
    return module, dock_widget, krita_instance


@pytest.mark.parametrize("filename", _DOCKER_MODULES)
def test_docker_overrides_canvas_changed(filename, monkeypatch):
    module, dock_widget, _krita_instance = _load(filename, monkeypatch)
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


def test_plugin_entry_point_registers_every_docker(monkeypatch):
    """Import __init__.py itself -- the exact path Krita's plugin loader takes."""
    dock_widget, krita_instance = _install_stub_krita_modules(monkeypatch)
    package_dir = _package_dir()
    package_name = "cel_shaded_generator"

    spec = importlib.util.spec_from_file_location(
        package_name, package_dir / "__init__.py", submodule_search_locations=[str(package_dir)]
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, package_name, package)
    spec.loader.exec_module(package)

    assert len(krita_instance.registered_factories) == 4
    registered_classes = {
        factory.docker_class for factory in krita_instance.registered_factories
    }
    for docker_class in registered_classes:
        assert issubclass(docker_class, dock_widget)
        assert "canvasChanged" in docker_class.__dict__, (
            f"{docker_class.__name__} is registered but does not override canvasChanged()"
        )
