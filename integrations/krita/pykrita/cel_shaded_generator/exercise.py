"""Krita document adapter for the first construction exercise."""

from __future__ import annotations

from pathlib import Path

EXERCISE_WIDTH = 1600
EXERCISE_HEIGHT = 2000
EXERCISE_RESOLUTION = 144.0
EXERCISE_TITLE = "Anime Head Construction — Attempt"


def create_exercise_document(application):
    """Create a predictable, unsaved exercise without touching existing documents."""
    window = application.activeWindow()
    if window is None:
        raise RuntimeError("Krita needs an active window before creating an exercise")
    document = application.createDocument(
        EXERCISE_WIDTH,
        EXERCISE_HEIGHT,
        EXERCISE_TITLE,
        "RGBA",
        "U8",
        "",
        EXERCISE_RESOLUTION,
    )
    if document is None:
        raise RuntimeError("Krita could not create the exercise document")

    root = document.rootNode()
    feedback = document.createNode("Tutor Feedback (locked)", "grouplayer")
    artwork = document.createNode("Artwork", "paintlayer")
    construction = document.createNode("Construction Guides", "paintlayer")
    if any(node is None for node in (feedback, artwork, construction)):
        raise RuntimeError("Krita could not create the exercise layers")
    feedback.setLocked(True)
    root.addChildNode(feedback, None)
    root.addChildNode(artwork, feedback)
    root.addChildNode(construction, artwork)
    window.addView(document)
    document.setActiveNode(construction)
    document.setModified(False)
    return document


def create_exercise_project(application, engine_client, directory, attempt_id):
    """Create and save one portable exercise project in an empty directory."""
    root = Path(directory).expanduser().resolve()
    if not root.is_dir() or any(root.iterdir()):
        raise ValueError("choose an existing empty project directory")
    document = create_exercise_document(application)
    artwork = root / "artwork"
    artwork.mkdir()
    document_path = artwork / "attempt-001.kra"
    if not document.saveAs(str(document_path)):
        raise RuntimeError("Krita could not save the exercise document")
    result = engine_client.create_exercise_project(
        "create-" + attempt_id,
        str(root),
        root.name or "Anime head practice",
        attempt_id,
    )
    document.setModified(False)
    return document, result
