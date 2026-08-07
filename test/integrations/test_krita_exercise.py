"""Headless contract tests for the Krita exercise-document adapter."""

import importlib.util
from pathlib import Path

import pytest


def _load_adapter():
    path = Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator/exercise.py"
    spec = importlib.util.spec_from_file_location("krita_exercise_adapter", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NodeStub:
    def __init__(self, name, kind):
        self.name = name
        self.kind = kind
        self.locked = False
        self.children = []

    def setLocked(self, locked):  # noqa: N802
        self.locked = locked

    def addChildNode(self, node, above):  # noqa: N802
        self.children.append((node, above))


class DocumentStub:
    def __init__(self):
        self.root = NodeStub("root", "root")
        self.active = None
        self.modified = True

    def rootNode(self):  # noqa: N802
        return self.root

    def createNode(self, name, kind):  # noqa: N802
        return NodeStub(name, kind)

    def setActiveNode(self, node):  # noqa: N802
        self.active = node

    def setModified(self, modified):  # noqa: N802
        self.modified = modified


class WindowStub:
    def __init__(self):
        self.views = []

    def addView(self, document):  # noqa: N802
        self.views.append(document)


class ApplicationStub:
    def __init__(self, window=True):
        self.window = WindowStub() if window else None
        self.created_with = None
        self.document = DocumentStub()

    def activeWindow(self):  # noqa: N802
        return self.window

    def createDocument(self, *arguments):  # noqa: N802
        self.created_with = arguments
        return self.document


def test_creates_unsaved_exercise_with_separated_layers():
    adapter = _load_adapter()
    application = ApplicationStub()
    document = adapter.create_exercise_document(application)

    assert application.created_with == (
        1600,
        2000,
        "Anime Head Construction — Attempt",
        "RGBA",
        "U8",
        "",
        144.0,
    )
    assert application.window.views == [document]
    assert [node.name for node, _ in document.root.children] == [
        "Tutor Feedback (locked)",
        "Artwork",
        "Construction Guides",
    ]
    assert document.root.children[0][0].locked
    assert document.active.name == "Construction Guides"
    assert document.modified is False


def test_refuses_creation_without_active_krita_window():
    adapter = _load_adapter()
    with pytest.raises(RuntimeError, match="active window"):
        adapter.create_exercise_document(ApplicationStub(window=False))
