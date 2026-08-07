"""Separate offline Krita Docker for semantic character-color authoring."""

from __future__ import annotations

import uuid
from pathlib import Path

from krita import DockWidget, Krita
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .color_masks import MASK_GROUP_NAME, PREVIEW_PREFIX, material_mask_name, palette_preview_bgra
from .engine_client import EngineClient
from .value_masks import find_named_node


class CharacterColorsDocker(DockWidget):
    """Author bibles and preview explicit material-mask palette roles."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Character Colors")
        container = QWidget(self)
        layout = QVBoxLayout(container)
        self._status = QLabel("Bind a portable project to begin.", container)
        self._status.setWordWrap(True)
        self._bibles = QComboBox(container)
        actions = (
            ("Bind Portable Project", self._bind_project),
            ("Import Reference Image", self._import_reference),
            ("Create / Replace Style Bible", self._author_bible),
            ("Create Material Mask Layers", self._create_masks),
            ("Preview Active Mask Palette Role", self._preview_palette),
            ("Accept Color Preview", self._accept_preview),
            ("Reject Color Preview", self._reject_preview),
        )
        layout.addWidget(self._bibles)
        for label, callback in actions:
            button = QPushButton(label, container)
            button.clicked.connect(callback)
            layout.addWidget(button)
        layout.addWidget(self._status)
        self.setWidget(container)
        self._project_directory = None
        self._references = []
        self._preview = None

    def _bind_project(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Portable Project")
        if not directory:
            return
        if not (Path(directory) / "project.json").is_file():
            self._status.setText("Selected directory has no portable project.json.")
            return
        self._project_directory = directory
        self._refresh_bibles()

    def _refresh_bibles(self):
        try:
            snapshot = EngineClient().project_progress_snapshot(
                str(uuid.uuid4()), self._project_directory
            )
        except (RuntimeError, ValueError) as error:
            self._status.setText("Could not read project: " + str(error))
            return
        self._bibles.clear()
        for bible in snapshot.get("style_bibles", []):
            self._bibles.addItem(
                bible["character_name"] + " — " + bible["style_name"], bible["asset_path"]
            )
        self._status.setText(f"Bound project with {self._bibles.count()} style bible(s).")

    def _import_reference(self):
        if self._project_directory is None:
            self._status.setText("Bind a portable project first.")
            return
        source, _ = QFileDialog.getOpenFileName(
            self, "Import Reference", "", "Images (*.png *.jpg *.jpeg *.webp *.tif *.tiff)"
        )
        if not source:
            return
        try:
            result = EngineClient().import_reference_asset(
                str(uuid.uuid4()), self._project_directory, source
            )
        except (RuntimeError, ValueError) as error:
            self._status.setText("Could not import reference: " + str(error))
            return
        self._references.append(result["asset_path"])
        self._status.setText("Imported project reference: " + result["asset_path"])

    def _author_bible(self):
        if self._project_directory is None:
            self._status.setText("Bind a portable project first.")
            return
        bible_id = self._text("Style Bible", "Lowercase kebab-case bible ID:")
        character = self._text("Style Bible", "Character name:")
        style = self._text("Style Bible", "Style name:")
        if None in (bible_id, character, style):
            return
        count, accepted = QInputDialog.getInt(
            self, "Materials", "Number of semantic materials:", 1, 1, 50, 1
        )
        if not accepted:
            return
        materials = []
        for index in range(count):
            material_id = self._text("Material", f"Material {index + 1} canonical ID:")
            label = self._text("Material", f"Material {index + 1} label:")
            local = self._text("Palette", "Local color (#RRGGBB):")
            light = self._text("Palette", "Light color (#RRGGBB):")
            shadow = self._text("Palette", "Shadow color (#RRGGBB):")
            if None in (material_id, label, local, light, shadow):
                return
            materials.append(
                {
                    "id": material_id,
                    "label": label,
                    "aliases": [],
                    "palette": {"local": local, "light": light, "shadow": shadow},
                }
            )
        references = [
            {"id": f"reference-{index + 1}", "label": Path(path).stem, "asset_path": path}
            for index, path in enumerate(self._references)
        ]
        payload = {
            "id": bible_id,
            "character_name": character,
            "style_name": style,
            "materials": materials,
            "reference_views": references,
            "recovery_revisions": 10,
            "schema_version": 1,
        }
        try:
            EngineClient().upsert_project_style_bible(
                str(uuid.uuid4()), self._project_directory, payload
            )
        except (RuntimeError, ValueError) as error:
            self._status.setText("Could not save style bible: " + str(error))
            return
        self._references.clear()
        self._refresh_bibles()

    def _create_masks(self):
        document = Krita.instance().activeDocument()
        bible = self._selected_bible()
        if document is None or bible is None:
            self._status.setText("Open a document and select a bound style bible first.")
            return
        root = document.rootNode()
        group = find_named_node(root, MASK_GROUP_NAME)
        if group is None:
            group = document.createNode(MASK_GROUP_NAME, "grouplayer")
            root.addChildNode(group, None)
        for material in bible["materials"]:
            name = material_mask_name(material["id"])
            if find_named_node(group, name) is None:
                group.addChildNode(document.createNode(name, "paintlayer"), None)
        document.refreshProjection()
        self._status.setText("Material mask layers are ready; paint alpha to define regions.")

    def _preview_palette(self):
        document = Krita.instance().activeDocument()
        bible = self._selected_bible()
        if document is None or bible is None:
            return
        node = document.activeNode()
        name = node.name() if node is not None else ""
        if not name.startswith("Material — "):
            self._status.setText("Select a Material — <canonical-id> mask layer.")
            return
        material_id = name[len("Material — ") :]
        material = next((item for item in bible["materials"] if item["id"] == material_id), None)
        if material is None:
            self._status.setText("Active mask does not exist in the selected bible.")
            return
        role, accepted = QInputDialog.getItem(
            self, "Palette Role", "Preview role:", list(material["palette"]), 0, False
        )
        if not accepted:
            return
        width, height = document.width(), document.height()
        raw = bytes(node.pixelData(0, 0, width, height))
        if len(raw) != width * height * 4:
            self._status.setText("Krita returned an unexpected mask buffer.")
            return
        pixels = palette_preview_bgra(raw[3::4], material["palette"][role])
        preview = document.createNode(PREVIEW_PREFIX + material_id + " — " + role, "paintlayer")
        document.rootNode().addChildNode(preview, None)
        preview.setPixelData(QByteArray(pixels), 0, 0, width, height)
        preview.setLocked(True)
        self._preview = preview
        document.refreshProjection()
        self._status.setText("Preview created; source mask and artwork are unchanged.")

    def _accept_preview(self):
        if self._preview is None:
            return
        self._preview.setName(self._preview.name().replace(PREVIEW_PREFIX, "Color Accepted — ", 1))
        self._preview.setLocked(True)
        self._preview = None
        self._status.setText("Color preview accepted as a separate locked layer.")

    def _reject_preview(self):
        if self._preview is None:
            return
        self._preview.remove()
        self._preview = None
        self._status.setText("Color preview rejected; artist layers were unchanged.")

    def _selected_bible(self):
        if self._project_directory is None or self._bibles.currentData() is None:
            return None
        try:
            return EngineClient().project_style_bible_payload(
                str(uuid.uuid4()), self._project_directory, self._bibles.currentData()
            )
        except (RuntimeError, ValueError) as error:
            self._status.setText("Could not load style bible: " + str(error))
            return None

    def _text(self, title, prompt):
        value, accepted = QInputDialog.getText(self, title, prompt)
        return value.strip() if accepted and value.strip() else None
