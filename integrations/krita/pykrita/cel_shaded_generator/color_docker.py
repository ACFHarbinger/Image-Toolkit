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
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .color_masks import (
    ACCEPTED_GROUP_NAME,
    ACCEPTED_PREFIX,
    MASK_GROUP_NAME,
    PREVIEW_PREFIX,
    material_mask_name,
    material_mask_parts,
    overlapping_materials,
    palette_preview_bgra,
    region_id_from_layer_name,
    union_alpha_buffers,
)
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
            ("Create Material Mask Variant", self._create_mask_variant),
            ("Assign Region Correspondence", self._assign_correspondence),
            ("Propagate Correspondence to Regions", self._propagate_correspondence),
            ("Preview Region Correspondence Color", self._preview_correspondence),
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
        label = self._text("Reference", "Reference label:", Path(source).stem)
        if label is None:
            return
        view_type, accepted = QInputDialog.getItem(
            self,
            "Reference",
            "Reference view type:",
            self._reference_view_types(),
            0,
            False,
        )
        if not accepted:
            return
        notes = self._text("Reference", "Reference notes (optional):", allow_empty=True)
        if notes is None:
            return
        self._references.append(
            {
                "asset_path": result["asset_path"],
                "label": label,
                "view_type": view_type,
                **({"notes": notes} if notes else {}),
            }
        )
        self._status.setText("Imported project reference: " + result["asset_path"])

    def _author_bible(self):
        if self._project_directory is None:
            self._status.setText("Bind a portable project first.")
            return
        existing = self._selected_bible() if self._bibles.count() else None
        bible_id = self._text(
            "Style Bible",
            "Lowercase kebab-case bible ID:",
            existing["id"] if existing else "",
        )
        character = self._text(
            "Style Bible", "Character name:", existing["character_name"] if existing else ""
        )
        style = self._text("Style Bible", "Style name:", existing["style_name"] if existing else "")
        if None in (bible_id, character, style):
            return
        count, accepted = QInputDialog.getInt(
            self,
            "Materials",
            "Number of semantic materials:",
            len(existing["materials"]) if existing else 1,
            1,
            50,
            1,
        )
        if not accepted:
            return
        materials = []
        for index in range(count):
            prior = (
                existing["materials"][index]
                if existing and index < len(existing["materials"])
                else None
            )
            material_id = self._text(
                "Material", f"Material {index + 1} canonical ID:", prior["id"] if prior else ""
            )
            label = self._text(
                "Material", f"Material {index + 1} label:", prior["label"] if prior else ""
            )
            aliases = self._text(
                "Material",
                "Comma-separated aliases (optional):",
                ", ".join(prior.get("aliases", [])) if prior else "",
                allow_empty=True,
            )
            local = self._text(
                "Palette", "Local color (#RRGGBB):", prior["palette"]["local"] if prior else ""
            )
            light = self._text(
                "Palette", "Light color (#RRGGBB):", prior["palette"]["light"] if prior else ""
            )
            shadow = self._text(
                "Palette", "Shadow color (#RRGGBB):", prior["palette"]["shadow"] if prior else ""
            )
            accent = self._text(
                "Palette",
                "Optional accent color (#RRGGBB or empty):",
                prior["palette"].get("accent") or "" if prior else "",
                allow_empty=True,
            )
            if None in (material_id, label, local, light, shadow):
                return
            palette = {"local": local, "light": light, "shadow": shadow}
            if accent:
                palette["accent"] = accent
            materials.append(
                {
                    "id": material_id,
                    "label": label,
                    "aliases": [item.strip() for item in aliases.split(",") if item.strip()],
                    "palette": palette,
                }
            )
        references = []
        for reference in existing.get("reference_views", []) if existing else []:
            edited = self._edit_reference(reference)
            if edited is None:
                return
            references.append(edited)
        used_reference_ids = {reference["id"] for reference in references}
        for reference in self._references:
            number = 1
            while f"reference-{number}" in used_reference_ids:
                number += 1
            reference_id = f"reference-{number}"
            used_reference_ids.add(reference_id)
            references.append({"id": reference_id, **reference})
        payload = {
            "id": bible_id,
            "character_name": character,
            "style_name": style,
            "materials": materials,
            "reference_views": references,
            "recovery_revisions": 10,
            "schema_version": 2,
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
            if group is None or not root.addChildNode(group, None):
                self._status.setText("Krita could not create the Material Masks group.")
                return
        for material in bible["materials"]:
            name = material_mask_name(material["id"])
            if find_named_node(group, name) is None:
                layer = document.createNode(name, "paintlayer")
                if layer is None or not group.addChildNode(layer, None):
                    self._status.setText("Krita could not create a material mask layer.")
                    return
        document.refreshProjection()
        self._status.setText("Material mask layers are ready; paint alpha to define regions.")

    def _create_mask_variant(self):
        document = Krita.instance().activeDocument()
        bible = self._selected_bible()
        if document is None or bible is None:
            self._status.setText("Open a document and select a bound style bible first.")
            return
        material_id, accepted = QInputDialog.getItem(
            self,
            "Material Mask Variant",
            "Canonical material:",
            [item["id"] for item in bible["materials"]],
            0,
            False,
        )
        if not accepted:
            return
        variant = self._text("Material Mask Variant", "Variant name:")
        if variant is None:
            return
        root = document.rootNode()
        group = find_named_node(root, MASK_GROUP_NAME)
        if group is None:
            group = document.createNode(MASK_GROUP_NAME, "grouplayer")
            if group is None or not root.addChildNode(group, None):
                self._status.setText("Krita could not create the Material Masks group.")
                return
        name = material_mask_name(material_id, variant)
        if find_named_node(group, name) is not None:
            self._status.setText("That material-mask variant already exists.")
            return
        layer = document.createNode(name, "paintlayer")
        if layer is None or not group.addChildNode(layer, None):
            self._status.setText("Krita could not create the material-mask variant.")
            return
        document.refreshProjection()
        self._status.setText("Created " + name + "; paint alpha to define its region.")

    def _preview_palette(self):
        document = Krita.instance().activeDocument()
        bible = self._selected_bible()
        if document is None or bible is None:
            return
        node = document.activeNode()
        try:
            material_id, _variant = material_mask_parts(node)
        except ValueError:
            self._status.setText("Select a Material — <canonical-id> mask layer.")
            return
        material = next((item for item in bible["materials"] if item["id"] == material_id), None)
        if material is None:
            self._status.setText("Active mask does not exist in the selected bible.")
            return
        if self._preview is not None:
            self._status.setText("Accept or reject the current color preview first.")
            return
        role, accepted = QInputDialog.getItem(
            self,
            "Palette Role",
            "Preview role:",
            [key for key, value in material["palette"].items() if value is not None],
            0,
            False,
        )
        if not accepted:
            return
        width, height = document.width(), document.height()
        raw = bytes(node.pixelData(0, 0, width, height))
        if len(raw) != width * height * 4:
            self._status.setText("Krita returned an unexpected mask buffer.")
            return
        mask_group = find_named_node(document.rootNode(), MASK_GROUP_NAME)
        masks = {}
        for item in bible["materials"]:
            mask_buffers = self._mask_buffers(mask_group, item["id"], width, height)
            if not mask_buffers:
                continue
            try:
                masks[item["id"]] = union_alpha_buffers(mask_buffers)
            except ValueError as error:
                self._status.setText("Could not combine material mask variants: " + str(error))
                return
        try:
            conflicts = overlapping_materials(material_id, masks)
        except ValueError as error:
            self._status.setText("Could not compare material masks: " + str(error))
            return
        if conflicts:
            details = ", ".join(
                f"{conflict_id} ({count} px)" for conflict_id, count in conflicts.items()
            )
            self._status.setText("Mask overlaps must be corrected: " + details + ".")
            return
        pixels = palette_preview_bgra(raw[3::4], material["palette"][role])
        if self._create_preview_layer(document, bible, material_id, role, pixels, width, height):
            self._status.setText("Preview created; source mask and artwork are unchanged.")

    def _assign_correspondence(self):
        document = Krita.instance().activeDocument()
        bible = self._selected_bible()
        if document is None or bible is None:
            self._status.setText("Open a document and select a bound style bible first.")
            return
        node = document.activeNode()
        if node is None:
            self._status.setText("Select the layer representing the target region.")
            return
        try:
            region_id = region_id_from_layer_name(node.name())
        except ValueError as error:
            self._status.setText("Could not derive a region id: " + str(error))
            return
        material_id, accepted = QInputDialog.getItem(
            self,
            "Region Correspondence",
            "Canonical material:",
            [item["id"] for item in bible["materials"]],
            0,
            False,
        )
        if not accepted:
            return
        role, accepted = QInputDialog.getItem(
            self,
            "Region Correspondence",
            "Palette role:",
            ["local", "light", "shadow", "accent"],
            0,
            False,
        )
        if not accepted:
            return
        panel_id = self._text(
            "Region Correspondence", "Optional panel/page id (kebab-case):", allow_empty=True
        )
        if panel_id is None:
            return
        correspondence_set = self._correspondence_set(bible["id"])
        entry = {
            "id": "correspondence-" + uuid.uuid4().hex[:8],
            "region_id": region_id,
            "material_id": material_id,
            "role": role,
        }
        if panel_id:
            entry["panel_id"] = panel_id
        correspondence_set["correspondences"].append(entry)
        try:
            EngineClient().upsert_project_correspondence_set(
                str(uuid.uuid4()), self._project_directory, correspondence_set
            )
        except (RuntimeError, ValueError) as error:
            self._status.setText("Could not save region correspondence: " + str(error))
            return
        self._status.setText(f"Assigned region '{region_id}' to {material_id}/{role}.")

    def _propagate_correspondence(self):
        bible = self._selected_bible()
        if bible is None:
            self._status.setText("Select a bound style bible first.")
            return
        asset_path = f"correspondence/{bible['id']}.json"
        try:
            correspondence_set = EngineClient().project_correspondence_set_payload(
                str(uuid.uuid4()), self._project_directory, asset_path
            )
        except (RuntimeError, ValueError) as error:
            self._status.setText("Assign at least one region correspondence first: " + str(error))
            return
        entries = correspondence_set.get("correspondences", [])
        if not entries:
            self._status.setText("No region correspondences exist to propagate.")
            return
        choices = [
            f"{item['id']} ({item['region_id']} → {item['material_id']}/{item['role']})"
            for item in entries
        ]
        choice, accepted = QInputDialog.getItem(
            self, "Propagate Correspondence", "Source assignment:", choices, 0, False
        )
        if not accepted:
            return
        source_id = choice.split(" ", 1)[0]
        targets_text = self._text("Propagate Correspondence", "Comma-separated target region ids:")
        if targets_text is None:
            return
        target_region_ids = [item.strip() for item in targets_text.split(",") if item.strip()]
        if not target_region_ids:
            self._status.setText("Enter at least one explicit target region id.")
            return
        try:
            propagated = EngineClient().propagate_project_correspondence(
                str(uuid.uuid4()),
                self._project_directory,
                asset_path,
                source_id,
                target_region_ids,
            )
        except (RuntimeError, ValueError) as error:
            self._status.setText("Could not propagate correspondence: " + str(error))
            return
        self._status.setText(
            f"Propagated to {len(target_region_ids)} region(s); set now has "
            f"{len(propagated['correspondences'])} correspondence(s)."
        )

    def _preview_correspondence(self):
        document = Krita.instance().activeDocument()
        bible = self._selected_bible()
        if document is None or bible is None:
            self._status.setText("Open a document and select a bound style bible first.")
            return
        if self._preview is not None:
            self._status.setText("Accept or reject the current color preview first.")
            return
        node = document.activeNode()
        if node is None:
            self._status.setText("Select the layer representing the target region.")
            return
        try:
            region_id = region_id_from_layer_name(node.name())
        except ValueError as error:
            self._status.setText("Could not derive a region id: " + str(error))
            return
        asset_path = f"correspondence/{bible['id']}.json"
        try:
            correspondence_set = EngineClient().project_correspondence_set_payload(
                str(uuid.uuid4()), self._project_directory, asset_path
            )
        except (RuntimeError, ValueError) as error:
            self._status.setText("No region correspondences are bound: " + str(error))
            return
        matches = [
            item
            for item in correspondence_set.get("correspondences", [])
            if item["region_id"] == region_id
        ]
        if len(matches) != 1:
            self._status.setText("Active region has no unambiguous correspondence assignment.")
            return
        correspondence = matches[0]
        material = next(
            (item for item in bible["materials"] if item["id"] == correspondence["material_id"]),
            None,
        )
        if material is None:
            self._status.setText("Assigned material no longer exists in the style bible.")
            return
        color = material["palette"].get(correspondence["role"])
        if color is None:
            self._status.setText("Assigned palette role is not defined for this material.")
            return
        width, height = document.width(), document.height()
        raw = bytes(node.pixelData(0, 0, width, height))
        if len(raw) != width * height * 4:
            self._status.setText("Krita returned an unexpected mask buffer.")
            return
        pixels = palette_preview_bgra(raw[3::4], color)
        material_id, role = correspondence["material_id"], correspondence["role"]
        if self._create_preview_layer(document, bible, material_id, role, pixels, width, height):
            self._status.setText(
                "Correspondence preview created; source region and artwork are unchanged."
            )

    def _correspondence_set(self, bible_id):
        asset_path = f"correspondence/{bible_id}.json"
        try:
            return EngineClient().project_correspondence_set_payload(
                str(uuid.uuid4()), self._project_directory, asset_path
            )
        except (RuntimeError, ValueError):
            return {
                "id": bible_id,
                "style_bible_id": bible_id,
                "correspondences": [],
                "recovery_revisions": 10,
                "schema_version": 1,
            }

    def _create_preview_layer(self, document, bible, material_id, role, pixels, width, height):
        preview = document.createNode(PREVIEW_PREFIX + material_id + " — " + role, "paintlayer")
        color_group = find_named_node(document.rootNode(), ACCEPTED_GROUP_NAME)
        if color_group is None:
            color_group = document.createNode(ACCEPTED_GROUP_NAME, "grouplayer")
            if color_group is None or not document.rootNode().addChildNode(color_group, None):
                self._status.setText("Krita could not create the Character Colors group.")
                return False
        if preview is None or not color_group.addChildNode(preview, None):
            self._status.setText("Krita could not create the color preview layer.")
            return False
        if not preview.setPixelData(QByteArray(pixels), 0, 0, width, height):
            preview.remove()
            self._status.setText("Krita could not write the color preview safely.")
            return False
        preview.setLocked(True)
        set_property = getattr(preview, "setProperty", None)
        if callable(set_property):
            set_property("cel_shaded_generator.style_bible_id", bible["id"])
        self._preview = preview
        document.refreshProjection()
        return True

    def _accept_preview(self):
        if self._preview is None:
            return
        self._preview.setName(self._preview.name().replace(PREVIEW_PREFIX, ACCEPTED_PREFIX, 1))
        self._preview.setLocked(False)
        self._preview = None
        self._status.setText("Color accepted as a separate editable Character Colors layer.")

    def _reject_preview(self):
        if self._preview is None:
            return
        if not self._preview.remove():
            self._status.setText("Krita could not remove the owned color preview.")
            return
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

    def _text(self, title, prompt, default="", allow_empty=False):
        value, accepted = QInputDialog.getText(self, title, prompt, QLineEdit.Normal, default)
        if not accepted:
            return None
        value = value.strip()
        return value if value or allow_empty else None

    @staticmethod
    def _reference_view_types():
        return ["front", "profile", "three-quarter", "expression", "costume-detail", "other"]

    def _edit_reference(self, reference):
        label = self._text("Reference", "Reference label:", reference["label"])
        if label is None:
            return None
        choices = self._reference_view_types()
        current = reference.get("view_type", "other")
        index = choices.index(current) if current in choices else choices.index("other")
        view_type, accepted = QInputDialog.getItem(
            self, "Reference", "Reference view type:", choices, index, False
        )
        if not accepted:
            return None
        notes = self._text(
            "Reference",
            "Reference notes (optional):",
            reference.get("notes") or "",
            allow_empty=True,
        )
        if notes is None:
            return None
        edited = {**reference, "label": label, "view_type": view_type}
        if notes:
            edited["notes"] = notes
        else:
            edited.pop("notes", None)
        return edited

    @staticmethod
    def _mask_buffers(root, material_id, width, height):
        if root is None:
            return []
        buffers = []
        for node in root.childNodes():
            try:
                node_material, _variant = material_mask_parts(node)
            except (AttributeError, ValueError):
                node_material = None
            if node_material == material_id:
                raw = bytes(node.pixelData(0, 0, width, height))
                if len(raw) != width * height * 4:
                    raise ValueError("Krita returned an unexpected material-mask buffer.")
                buffers.append(raw[3::4])
            buffers.extend(CharacterColorsDocker._mask_buffers(node, material_id, width, height))
        return buffers

    def canvasChanged(self, canvas) -> None:  # noqa: N802
        """Krita callback; this docker does not inspect the canvas."""
