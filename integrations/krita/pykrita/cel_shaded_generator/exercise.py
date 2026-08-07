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
VOLUME_JAW_EXERCISE_ID = "anime-head-volume-jaw"
VOLUME_JAW_WIDTH = 2800
VOLUME_JAW_HEIGHT = 1600
VOLUME_JAW_TITLE = "Cranial Volume and Jaw Variation — Design Sheet"
VOLUME_JAW_VIEWS = (
    "01 Neutral Front Construction",
    "02 Youthful Soft Front Construction",
    "03 Long Tapered Front Construction",
    "04 Broad Angular Front Construction",
    "05 Selected Variant Right Three-Quarter Construction",
)
EYE_EXERCISE_ID = "anime-head-eyes"
EYE_EXERCISE_WIDTH = 2400
EYE_EXERCISE_HEIGHT = 1600
EYE_EXERCISE_TITLE = "Eye Placement and Perspective — Front-to-Turned Sheet"
EYE_EXERCISE_VIEWS = (
    "01 Neutral Front Eye Structure",
    "02 Stylized Front Expression",
    "03 Neutral Right Three-Quarter Eye Structure",
    "04 Stylized Right Three-Quarter Expression",
)
FEATURE_EXERCISE_ID = "anime-head-features"
FEATURE_EXERCISE_WIDTH = 2400
FEATURE_EXERCISE_HEIGHT = 1800
FEATURE_EXERCISE_TITLE = "Nose, Mouth, and Ear Placement — Front-to-Turned Matrix"
FEATURE_EXERCISE_VIEWS = (
    "01 Front Nose and Muzzle Construction",
    "02 Front Mouth Construction",
    "03 Front Ear Construction",
    "04 Right Three-Quarter Nose and Muzzle Construction",
    "05 Right Three-Quarter Mouth Construction",
    "06 Right Three-Quarter Ear Construction",
)
ASYMMETRY_EXERCISE_ID = "anime-head-asymmetry"
ASYMMETRY_EXERCISE_WIDTH = 2600
ASYMMETRY_EXERCISE_HEIGHT = 1800
ASYMMETRY_EXERCISE_TITLE = "Controlled Asymmetry — Cause and Transfer Sheet"
ASYMMETRY_EXERCISE_VIEWS = (
    "01 Symmetric Front Control",
    "02 Corrected Accidental Drift",
    "03 Persistent Design Asymmetry",
    "04 Expression Asymmetry",
    "05 Symmetric Right Three-Quarter Control",
    "06 Transferred Right Three-Quarter Asymmetry",
)
VARIATION_EXERCISE_ID = "anime-head-variation"
VARIATION_EXERCISE_WIDTH = 2600
VARIATION_EXERCISE_HEIGHT = 1800
VARIATION_EXERCISE_TITLE = "Character Variation and Identity Retention — Model Sheet"
VARIATION_EXERCISE_VIEWS = (
    "01 Undecorated Identity Baseline",
    "02 Proportion Variant",
    "03 Feature Shape Variant",
    "04 Age and Style Variant",
    "05 Selected Front Identity Reconstruction",
    "06 Selected Right Three-Quarter Identity Check",
)
VALUE_EXERCISE_ID = "anime-head-cel-values"
VALUE_EXERCISE_WIDTH = 2600
VALUE_EXERCISE_HEIGHT = 1800
VALUE_EXERCISE_TITLE = "Cel-Shaded Value Grouping — Light and Form Sheet"
VALUE_EXERCISE_VIEWS = (
    "01 Light Statement and Plane Map",
    "02 Front Two-Value Mask",
    "03 Front Cast-Shadow Audit",
    "04 Restrained Three-Value Pass",
    "05 Right Three-Quarter Two-Value Transfer",
    "06 Front and Turned Lighting Consistency",
)
CAPSTONE_EXERCISE_ID = "anime-head-review"
CAPSTONE_EXERCISE_WIDTH = 3200
CAPSTONE_EXERCISE_HEIGHT = 2000
CAPSTONE_EXERCISE_TITLE = "Anime Head Learning Capstone — Review and Revision Sheet"
CAPSTONE_EXERCISE_VIEWS = (
    "01 Brief and Identity Specification",
    "02 Front Construction",
    "03 Right Three-Quarter Construction",
    "04 Expression Asymmetry and Value Pass",
    "05 Tutor Review and Correction Pass",
    "06 Final Comparison and Self-Review",
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


def create_volume_jaw_exercise_document(application):
    """Create the five-area variation and rotation design sheet."""
    window = application.activeWindow()
    if window is None:
        raise RuntimeError("Krita needs an active window before creating an exercise")
    document = application.createDocument(
        VOLUME_JAW_WIDTH,
        VOLUME_JAW_HEIGHT,
        VOLUME_JAW_TITLE,
        "RGBA",
        "U8",
        "",
        EXERCISE_RESOLUTION,
    )
    if document is None:
        raise RuntimeError("Krita could not create the cranial/jaw exercise document")
    root = document.rootNode()
    feedback = document.createNode("Tutor Feedback (locked)", "grouplayer")
    layout = document.createNode("Tutor Variation Layout (locked)", "vectorlayer")
    work_layers = [document.createNode(name, "paintlayer") for name in VOLUME_JAW_VIEWS]
    if feedback is None or layout is None or any(node is None for node in work_layers):
        raise RuntimeError("Krita could not create the cranial/jaw exercise layers")
    layout.addShapesFromSvg(_five_cell_layout_svg(VOLUME_JAW_WIDTH, VOLUME_JAW_VIEWS))
    layout.setLocked(True)
    feedback.setLocked(True)
    root.addChildNode(feedback, None)
    feedback.addChildNode(layout, None)
    above = feedback
    for node in work_layers:
        root.addChildNode(node, above)
        above = node
    window.addView(document)
    document.setActiveNode(work_layers[0])
    document.setModified(False)
    return document


def create_eye_exercise_document(application):
    """Create four separate front-to-turned eye-construction work areas."""
    window = application.activeWindow()
    if window is None:
        raise RuntimeError("Krita needs an active window before creating an exercise")
    document = application.createDocument(
        EYE_EXERCISE_WIDTH,
        EYE_EXERCISE_HEIGHT,
        EYE_EXERCISE_TITLE,
        "RGBA",
        "U8",
        "",
        EXERCISE_RESOLUTION,
    )
    if document is None:
        raise RuntimeError("Krita could not create the eye exercise document")
    root = document.rootNode()
    feedback = document.createNode("Tutor Feedback (locked)", "grouplayer")
    layout = document.createNode("Tutor Eye Progression Layout (locked)", "vectorlayer")
    work_layers = [document.createNode(name, "paintlayer") for name in EYE_EXERCISE_VIEWS]
    if feedback is None or layout is None or any(node is None for node in work_layers):
        raise RuntimeError("Krita could not create the eye exercise layers")
    layout.addShapesFromSvg(_four_cell_eye_layout_svg())
    layout.setLocked(True)
    feedback.setLocked(True)
    root.addChildNode(feedback, None)
    feedback.addChildNode(layout, None)
    above = feedback
    for node in work_layers:
        root.addChildNode(node, above)
        above = node
    window.addView(document)
    document.setActiveNode(work_layers[0])
    document.setModified(False)
    return document


def create_feature_exercise_document(application):
    """Create equal front/turned practice areas for nose, mouth, and ears."""
    window = application.activeWindow()
    if window is None:
        raise RuntimeError("Krita needs an active window before creating an exercise")
    document = application.createDocument(
        FEATURE_EXERCISE_WIDTH,
        FEATURE_EXERCISE_HEIGHT,
        FEATURE_EXERCISE_TITLE,
        "RGBA",
        "U8",
        "",
        EXERCISE_RESOLUTION,
    )
    if document is None:
        raise RuntimeError("Krita could not create the feature exercise document")
    root = document.rootNode()
    feedback = document.createNode("Tutor Feedback (locked)", "grouplayer")
    layout = document.createNode("Tutor Feature Matrix Layout (locked)", "vectorlayer")
    work_layers = [document.createNode(name, "paintlayer") for name in FEATURE_EXERCISE_VIEWS]
    if feedback is None or layout is None or any(node is None for node in work_layers):
        raise RuntimeError("Krita could not create the feature exercise layers")
    layout.addShapesFromSvg(_feature_matrix_layout_svg())
    layout.setLocked(True)
    feedback.setLocked(True)
    root.addChildNode(feedback, None)
    feedback.addChildNode(layout, None)
    above = feedback
    for node in work_layers:
        root.addChildNode(node, above)
        above = node
    window.addView(document)
    document.setActiveNode(work_layers[0])
    document.setModified(False)
    return document


def create_asymmetry_exercise_document(application):
    """Create a six-stage sheet separating intentional asymmetry from drift."""
    window = application.activeWindow()
    if window is None:
        raise RuntimeError("Krita needs an active window before creating an exercise")
    document = application.createDocument(
        ASYMMETRY_EXERCISE_WIDTH,
        ASYMMETRY_EXERCISE_HEIGHT,
        ASYMMETRY_EXERCISE_TITLE,
        "RGBA",
        "U8",
        "",
        EXERCISE_RESOLUTION,
    )
    if document is None:
        raise RuntimeError("Krita could not create the asymmetry exercise document")
    root = document.rootNode()
    feedback = document.createNode("Tutor Feedback (locked)", "grouplayer")
    layout = document.createNode("Tutor Asymmetry Layout (locked)", "vectorlayer")
    work_layers = [document.createNode(name, "paintlayer") for name in ASYMMETRY_EXERCISE_VIEWS]
    if feedback is None or layout is None or any(node is None for node in work_layers):
        raise RuntimeError("Krita could not create the asymmetry exercise layers")
    layout.addShapesFromSvg(_asymmetry_layout_svg())
    layout.setLocked(True)
    feedback.setLocked(True)
    root.addChildNode(feedback, None)
    feedback.addChildNode(layout, None)
    above = feedback
    for node in work_layers:
        root.addChildNode(node, above)
        above = node
    window.addView(document)
    document.setActiveNode(work_layers[0])
    document.setModified(False)
    return document


def create_variation_exercise_document(application):
    """Create a six-stage identity generation and retention model sheet."""
    window = application.activeWindow()
    if window is None:
        raise RuntimeError("Krita needs an active window before creating an exercise")
    document = application.createDocument(
        VARIATION_EXERCISE_WIDTH,
        VARIATION_EXERCISE_HEIGHT,
        VARIATION_EXERCISE_TITLE,
        "RGBA",
        "U8",
        "",
        EXERCISE_RESOLUTION,
    )
    if document is None:
        raise RuntimeError("Krita could not create the variation exercise document")
    root = document.rootNode()
    feedback = document.createNode("Tutor Feedback (locked)", "grouplayer")
    layout = document.createNode("Tutor Identity Model-Sheet Layout (locked)", "vectorlayer")
    work_layers = [document.createNode(name, "paintlayer") for name in VARIATION_EXERCISE_VIEWS]
    if feedback is None or layout is None or any(node is None for node in work_layers):
        raise RuntimeError("Krita could not create the variation exercise layers")
    layout.addShapesFromSvg(_six_cell_layout_svg(VARIATION_EXERCISE_VIEWS))
    layout.setLocked(True)
    feedback.setLocked(True)
    root.addChildNode(feedback, None)
    feedback.addChildNode(layout, None)
    above = feedback
    for node in work_layers:
        root.addChildNode(node, above)
        above = node
    window.addView(document)
    document.setActiveNode(work_layers[0])
    document.setModified(False)
    return document


def _create_six_stage_document(application, width, height, title, views, layout_name):
    window = application.activeWindow()
    if window is None:
        raise RuntimeError("Krita needs an active window before creating an exercise")
    document = application.createDocument(
        width, height, title, "RGBA", "U8", "", EXERCISE_RESOLUTION
    )
    if document is None:
        raise RuntimeError("Krita could not create the six-stage exercise document")
    root = document.rootNode()
    feedback = document.createNode("Tutor Feedback (locked)", "grouplayer")
    layout = document.createNode(layout_name, "vectorlayer")
    work_layers = [document.createNode(name, "paintlayer") for name in views]
    if feedback is None or layout is None or any(node is None for node in work_layers):
        raise RuntimeError("Krita could not create the six-stage exercise layers")
    layout.addShapesFromSvg(_six_cell_layout_svg(views, width, height))
    layout.setLocked(True)
    feedback.setLocked(True)
    root.addChildNode(feedback, None)
    feedback.addChildNode(layout, None)
    above = feedback
    for node in work_layers:
        root.addChildNode(node, above)
        above = node
    window.addView(document)
    document.setActiveNode(work_layers[0])
    document.setModified(False)
    return document


def create_value_exercise_document(application):
    return _create_six_stage_document(
        application,
        VALUE_EXERCISE_WIDTH,
        VALUE_EXERCISE_HEIGHT,
        VALUE_EXERCISE_TITLE,
        VALUE_EXERCISE_VIEWS,
        "Tutor Cel-Value Layout (locked)",
    )


def create_capstone_exercise_document(application):
    return _create_six_stage_document(
        application,
        CAPSTONE_EXERCISE_WIDTH,
        CAPSTONE_EXERCISE_HEIGHT,
        CAPSTONE_EXERCISE_TITLE,
        CAPSTONE_EXERCISE_VIEWS,
        "Tutor Capstone Layout (locked)",
    )


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
    elif exercise_id == VOLUME_JAW_EXERCISE_ID:
        document = create_volume_jaw_exercise_document(application)
    elif exercise_id == EYE_EXERCISE_ID:
        document = create_eye_exercise_document(application)
    elif exercise_id == FEATURE_EXERCISE_ID:
        document = create_feature_exercise_document(application)
    elif exercise_id == ASYMMETRY_EXERCISE_ID:
        document = create_asymmetry_exercise_document(application)
    elif exercise_id == VARIATION_EXERCISE_ID:
        document = create_variation_exercise_document(application)
    elif exercise_id == VALUE_EXERCISE_ID:
        document = create_value_exercise_document(application)
    elif exercise_id == CAPSTONE_EXERCISE_ID:
        document = create_capstone_exercise_document(application)
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


def _five_cell_layout_svg(width, labels):
    cell_width = width // 5
    cells = []
    for index, label in enumerate(labels):
        x = 30 + index * cell_width
        short = label.split(" Construction")[0][3:].upper()
        cells.append(
            f'<rect x="{x}" y="120" width="{cell_width - 60}" height="1360" rx="18" '
            'fill="none" stroke="#8090a0" stroke-width="5" stroke-dasharray="18 14"/>'
            f'<text x="{x + (cell_width - 60) // 2}" y="85" text-anchor="middle" '
            f'font-family="sans-serif" font-size="32" fill="#506070">{short}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="1600" '
        f'viewBox="0 0 {width} 1600">' + "".join(cells) + "</svg>"
    )


def _four_cell_eye_layout_svg():
    labels = (
        "1. FRONT STRUCTURE",
        "2. FRONT STYLE + EXPRESSION",
        "3. 3/4 STRUCTURE",
        "4. 3/4 STYLE + EXPRESSION",
    )
    cells = []
    for index, label in enumerate(labels):
        x = 30 + index * 600
        cells.append(
            f'<rect x="{x}" y="120" width="540" height="1360" rx="18" '
            'fill="none" stroke="#8090a0" stroke-width="5" stroke-dasharray="18 14"/>'
            f'<text x="{x + 270}" y="82" text-anchor="middle" '
            f'font-family="sans-serif" font-size="28" fill="#506070">{label}</text>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="1600" '
        'viewBox="0 0 2400 1600">' + "".join(cells) + "</svg>"
    )


def _feature_matrix_layout_svg():
    columns = ("NOSE + MUZZLE", "MOUTH", "EAR")
    cells = []
    for row, view in enumerate(("FRONT", "RIGHT THREE-QUARTER")):
        y = 120 + row * 830
        cells.append(
            f'<text x="45" y="{y + 380}" font-family="sans-serif" font-size="30" '
            f'fill="#506070" transform="rotate(-90 45 {y + 380})">{view}</text>'
        )
        for column, feature in enumerate(columns):
            x = 90 + column * 770
            cells.append(
                f'<rect x="{x}" y="{y}" width="710" height="720" rx="18" '
                'fill="none" stroke="#8090a0" stroke-width="5" '
                'stroke-dasharray="18 14"/>'
                f'<text x="{x + 355}" y="{y - 25}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="30" fill="#506070">{feature}</text>'
            )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="1800" '
        'viewBox="0 0 2400 1800">' + "".join(cells) + "</svg>"
    )


def _asymmetry_layout_svg():
    labels = (
        "SYMMETRIC CONTROL",
        "CORRECTED DRIFT",
        "DESIGN ASYMMETRY",
        "EXPRESSION ASYMMETRY",
        "SYMMETRIC 3/4 CONTROL",
        "TRANSFERRED 3/4 ASYMMETRY",
    )
    cells = []
    for index, label in enumerate(labels):
        column, row = index % 3, index // 3
        x, y = 50 + column * 850, 120 + row * 830
        cells.append(
            f'<rect x="{x}" y="{y}" width="800" height="720" rx="18" '
            'fill="none" stroke="#8090a0" stroke-width="5" stroke-dasharray="18 14"/>'
            f'<text x="{x + 400}" y="{y - 28}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="29" fill="#506070">{label}</text>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="2600" height="1800" '
        'viewBox="0 0 2600 1800">' + "".join(cells) + "</svg>"
    )


def _six_cell_layout_svg(labels, width=2600, height=1800):
    cells = []
    column_width = width / 3
    row_height = height / 2
    for index, label in enumerate(labels):
        column, row = index % 3, index // 3
        x, y = 50 + column * column_width, 120 + row * row_height
        short = label[3:].upper()
        cells.append(
            f'<rect x="{x}" y="{y}" width="{column_width - 70}" '
            f'height="{row_height - 180}" rx="18" '
            'fill="none" stroke="#8090a0" stroke-width="5" stroke-dasharray="18 14"/>'
            f'<text x="{x + (column_width - 70) / 2}" y="{y - 28}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="25" fill="#506070">{short}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">' + "".join(cells) + "</svg>"
    )
