"""Tests for ChapterQueueDocker's path-resolution logic."""

import importlib.util
import sys
import types
from pathlib import Path


def _load_chapter_docker(monkeypatch):
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

    qtwidgets = types.ModuleType("PyQt5.QtWidgets")
    for name in (
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
    pyqt5.QtWidgets = qtwidgets

    monkeypatch.setitem(sys.modules, "krita", krita_module)
    monkeypatch.setitem(sys.modules, "PyQt5", pyqt5)
    monkeypatch.setitem(sys.modules, "PyQt5.QtWidgets", qtwidgets)

    package_dir = (
        Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator"
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
    return module.ChapterQueueDocker


def test_relative_to_project_resolves_nested_paths(monkeypatch, tmp_path):
    docker = _load_chapter_docker(monkeypatch)
    project_dir = tmp_path / "project"
    pages_dir = project_dir / "pages"
    pages_dir.mkdir(parents=True)
    page = pages_dir / "01.kra"
    page.write_bytes(b"page")

    fake_self = types.SimpleNamespace(_project_directory=str(project_dir))
    assert docker._relative_to_project(fake_self, str(page)) == "pages/01.kra"


def test_relative_to_project_rejects_paths_outside_the_project(monkeypatch, tmp_path):
    docker = _load_chapter_docker(monkeypatch)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    outside = tmp_path / "outside.kra"
    outside.write_bytes(b"page")

    fake_self = types.SimpleNamespace(_project_directory=str(project_dir))
    assert docker._relative_to_project(fake_self, str(outside)) is None
