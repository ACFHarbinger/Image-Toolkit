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
        self.svg = None

    def setLocked(self, locked):  # noqa: N802
        self.locked = locked

    def addChildNode(self, node, above):  # noqa: N802
        self.children.append((node, above))

    def addShapesFromSvg(self, svg):  # noqa: N802
        self.svg = svg


class DocumentStub:
    def __init__(self):
        self.root = NodeStub("root", "root")
        self.active = None
        self.modified = True
        self.saved_as = None

    def rootNode(self):  # noqa: N802
        return self.root

    def createNode(self, name, kind):  # noqa: N802
        return NodeStub(name, kind)

    def setActiveNode(self, node):  # noqa: N802
        self.active = node

    def setModified(self, modified):  # noqa: N802
        self.modified = modified

    def saveAs(self, path):  # noqa: N802
        self.saved_as = path
        Path(path).write_bytes(b"document")
        return True


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


class EngineStub:
    def create_exercise_project(self, request_id, directory, title, attempt_id, exercise_id):
        assert request_id == "create-attempt-1"
        assert title == Path(directory).name
        return {
            "project_id": "project-1",
            "attempt_id": attempt_id,
            "exercise_id": exercise_id,
        }


def test_creates_saved_portable_project_binding(tmp_path):
    adapter = _load_adapter()
    application = ApplicationStub()
    document, result = adapter.create_exercise_project(
        application, EngineStub(), tmp_path, "attempt-1"
    )
    assert document.saved_as == str(tmp_path / "artwork/attempt-001.kra")
    assert result == {
        "project_id": "project-1",
        "attempt_id": "attempt-1",
        "exercise_id": "anime-head-front-construction",
    }


def test_creates_landscape_five_view_orientation_sheet():
    adapter = _load_adapter()
    application = ApplicationStub()

    document = adapter.create_orientation_exercise_document(application)

    assert application.created_with[:3] == (
        2600,
        1600,
        "Anime Head Orientation — Five-View Rotation Sheet",
    )
    assert [node.name for node, _ in document.root.children] == [
        "Tutor Feedback (locked)",
        "01 Left Profile Construction",
        "02 Left Three-Quarter Construction",
        "03 Front Construction",
        "04 Right Three-Quarter Construction",
        "05 Right Profile Construction",
    ]
    feedback = document.root.children[0][0]
    layout = feedback.children[0][0]
    assert layout.name == "Tutor Rotation Layout (locked)"
    assert layout.locked
    assert "LEFT PROFILE" in layout.svg
    assert document.active.name == "03 Front Construction"


def test_creates_five_area_cranial_and_jaw_design_sheet():
    adapter = _load_adapter()
    application = ApplicationStub()

    document = adapter.create_volume_jaw_exercise_document(application)

    assert application.created_with[:3] == (
        2800,
        1600,
        "Cranial Volume and Jaw Variation — Design Sheet",
    )
    assert [node.name for node, _ in document.root.children] == [
        "Tutor Feedback (locked)",
        "01 Neutral Front Construction",
        "02 Youthful Soft Front Construction",
        "03 Long Tapered Front Construction",
        "04 Broad Angular Front Construction",
        "05 Selected Variant Right Three-Quarter Construction",
    ]
    layout = document.root.children[0][0].children[0][0]
    assert layout.name == "Tutor Variation Layout (locked)"
    assert layout.locked
    assert "NEUTRAL FRONT" in layout.svg
    assert "SELECTED VARIANT RIGHT THREE-QUARTER" in layout.svg
    assert document.active.name == "01 Neutral Front Construction"


def test_creates_four_area_eye_progression_sheet():
    adapter = _load_adapter()
    application = ApplicationStub()

    document = adapter.create_eye_exercise_document(application)

    assert application.created_with[:3] == (
        2400,
        1600,
        "Eye Placement and Perspective — Front-to-Turned Sheet",
    )
    assert [node.name for node, _ in document.root.children] == [
        "Tutor Feedback (locked)",
        "01 Neutral Front Eye Structure",
        "02 Stylized Front Expression",
        "03 Neutral Right Three-Quarter Eye Structure",
        "04 Stylized Right Three-Quarter Expression",
    ]
    layout = document.root.children[0][0].children[0][0]
    assert layout.name == "Tutor Eye Progression Layout (locked)"
    assert layout.locked
    assert "FRONT STRUCTURE" in layout.svg
    assert "3/4 STYLE + EXPRESSION" in layout.svg
    assert document.active.name == "01 Neutral Front Eye Structure"


def test_creates_equal_nose_mouth_ear_feature_matrix():
    adapter = _load_adapter()
    application = ApplicationStub()

    document = adapter.create_feature_exercise_document(application)

    assert application.created_with[:3] == (
        2400,
        1800,
        "Nose, Mouth, and Ear Placement — Front-to-Turned Matrix",
    )
    assert [node.name for node, _ in document.root.children] == [
        "Tutor Feedback (locked)",
        "01 Front Nose and Muzzle Construction",
        "02 Front Mouth Construction",
        "03 Front Ear Construction",
        "04 Right Three-Quarter Nose and Muzzle Construction",
        "05 Right Three-Quarter Mouth Construction",
        "06 Right Three-Quarter Ear Construction",
    ]
    layout = document.root.children[0][0].children[0][0]
    assert layout.name == "Tutor Feature Matrix Layout (locked)"
    assert layout.locked
    assert "NOSE + MUZZLE" in layout.svg
    assert "RIGHT THREE-QUARTER" in layout.svg
    assert document.active.name == "01 Front Nose and Muzzle Construction"


def test_creates_six_stage_controlled_asymmetry_sheet():
    adapter = _load_adapter()
    application = ApplicationStub()
    document = adapter.create_asymmetry_exercise_document(application)

    assert application.created_with[:3] == (
        2600,
        1800,
        "Controlled Asymmetry — Cause and Transfer Sheet",
    )
    assert [node.name for node, _ in document.root.children] == [
        "Tutor Feedback (locked)",
        "01 Symmetric Front Control",
        "02 Corrected Accidental Drift",
        "03 Persistent Design Asymmetry",
        "04 Expression Asymmetry",
        "05 Symmetric Right Three-Quarter Control",
        "06 Transferred Right Three-Quarter Asymmetry",
    ]
    layout = document.root.children[0][0].children[0][0]
    assert layout.locked
    assert "SYMMETRIC CONTROL" in layout.svg
    assert "TRANSFERRED 3/4 ASYMMETRY" in layout.svg


def test_creates_character_variation_identity_model_sheet():
    adapter = _load_adapter()
    application = ApplicationStub()
    document = adapter.create_variation_exercise_document(application)

    assert application.created_with[:3] == (
        2600,
        1800,
        "Character Variation and Identity Retention — Model Sheet",
    )
    assert [node.name for node, _ in document.root.children] == [
        "Tutor Feedback (locked)",
        "01 Undecorated Identity Baseline",
        "02 Proportion Variant",
        "03 Feature Shape Variant",
        "04 Age and Style Variant",
        "05 Selected Front Identity Reconstruction",
        "06 Selected Right Three-Quarter Identity Check",
    ]
    layout = document.root.children[0][0].children[0][0]
    assert layout.locked
    assert "UNDECORATED IDENTITY BASELINE" in layout.svg
    assert "SELECTED RIGHT THREE-QUARTER IDENTITY CHECK" in layout.svg


def test_portable_project_requires_empty_directory(tmp_path):
    adapter = _load_adapter()
    (tmp_path / "unrelated").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        adapter.create_exercise_project(ApplicationStub(), EngineStub(), tmp_path, "attempt-1")
