"""Krita document adapter for the first construction exercise."""

from __future__ import annotations

from pathlib import Path

EXERCISE_WIDTH = 1600
EXERCISE_HEIGHT = 2000
EXERCISE_RESOLUTION = 144.0
EXERCISE_TITLE = "Anime Head Construction — Attempt"
FRONT_EXERCISE_ID = "anime-head-front-construction"
ORIENTATION_EXERCISE_ID = "anime-head-orientation"
ORIENTATION_WIDTH = 2600
ORIENTATION_HEIGHT = 1600
ORIENTATION_TITLE = "Anime Head Orientation — Five-View Rotation Sheet"
ORIENTATION_VIEWS = (
    "01 Left Profile Construction",
    "02 Left Three-Quarter Construction",
    "03 Front Construction",
    "04 Right Three-Quarter Construction",
    "05 Right Profile Construction",
)


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


def create_orientation_exercise_document(application):
    """Create a landscape five-view sheet with labeled, separate work layers."""
    window = application.activeWindow()
    if window is None:
        raise RuntimeError("Krita needs an active window before creating an exercise")
    document = application.createDocument(
        ORIENTATION_WIDTH,
        ORIENTATION_HEIGHT,
        ORIENTATION_TITLE,
        "RGBA",
        "U8",
        "",
        EXERCISE_RESOLUTION,
    )
    if document is None:
        raise RuntimeError("Krita could not create the orientation exercise document")
    root = document.rootNode()
    feedback = document.createNode("Tutor Feedback (locked)", "grouplayer")
    layout = document.createNode("Tutor Rotation Layout (locked)", "vectorlayer")
    work_layers = [document.createNode(name, "paintlayer") for name in ORIENTATION_VIEWS]
    if feedback is None or layout is None or any(node is None for node in work_layers):
        raise RuntimeError("Krita could not create the orientation exercise layers")
    layout.addShapesFromSvg(_orientation_layout_svg())
    layout.setLocked(True)
    feedback.setLocked(True)
    root.addChildNode(feedback, None)
    feedback.addChildNode(layout, None)
    above = feedback
    for node in work_layers:
        root.addChildNode(node, above)
        above = node
    window.addView(document)
    document.setActiveNode(work_layers[2])
    document.setModified(False)
    return document


def create_exercise_project(
    application, engine_client, directory, attempt_id, exercise_id=FRONT_EXERCISE_ID
):
    """Create and save one portable exercise project in an empty directory."""
    root = Path(directory).expanduser().resolve()
    if not root.is_dir() or any(root.iterdir()):
        raise ValueError("choose an existing empty project directory")
    if exercise_id == FRONT_EXERCISE_ID:
        document = create_exercise_document(application)
    elif exercise_id == ORIENTATION_EXERCISE_ID:
        document = create_orientation_exercise_document(application)
    else:
        raise ValueError("the selected lesson has no exercise template yet")
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
        exercise_id,
    )
    document.setModified(False)
    return document, result


def _orientation_layout_svg():
    labels = (
        "LEFT PROFILE",
        "LEFT 3/4",
        "FRONT",
        "RIGHT 3/4",
        "RIGHT PROFILE",
    )
    cells = []
    for index, label in enumerate(labels):
        x = 40 + index * 510
        cells.append(
            f'<rect x="{x}" y="120" width="470" height="1360" rx="18" '
            'fill="none" stroke="#8090a0" stroke-width="5" stroke-dasharray="18 14"/>'
            f'<text x="{x + 235}" y="85" text-anchor="middle" '
            f'font-family="sans-serif" font-size="42" fill="#506070">{label}</text>'
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="2600" height="1600" '
        'viewBox="0 0 2600 1600">' + "".join(cells) + "</svg>"
    )
    return svg
