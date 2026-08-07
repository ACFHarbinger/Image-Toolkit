"""Krita document adapter for the first construction exercise."""

from __future__ import annotations

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
