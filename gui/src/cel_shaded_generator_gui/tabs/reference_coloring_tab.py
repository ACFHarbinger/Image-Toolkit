"""Standalone Reference Coloring editor tab -- canvas + layer stack
foundation, a brush paint tool, undo/redo, non-destructive layer masks,
line-art segmentation, and palette application (roadmap: standalone
editor, gate-5 exception; see ``docs/moon/roadmaps/engine_architecture.md``).

Create a blank canvas of a chosen size, add/remove/reorder/show-hide
layers, select a layer and paint on it with a solid-color circular brush,
undo/redo any of the above, attach a mask to a layer to paint which of its
pixels show through, segment a line-art layer's enclosed regions into
distinctly colored region layers (reusing the same deterministic
``colorization.segmentation`` algorithm the Line Art Segmentation Krita
Docker uses), bind a portable style bible (``colorization.style_bible``,
reused the same way) to recolor a region layer with one of its materials'
palette roles, and assign+rank region-to-material correspondences
(``colorization.correspondence``/``colorization.confidence``, reused the
same way the Krita Character Colors Docker's confidence-ranked material
dropdown does) so later segmented regions can suggest a default material
from already-assigned neighbors, and save/load a canvas document to a plain
directory so work survives closing the app. Correspondence assignment
optionally binds into a portable ``project`` (``logic/src/project``, the same
package the Krita tutor's lesson flow uses). When a project is bound and
a style bible attached to it, Suggest Material/Assign Correspondence
delegate to ``project.rank_correspondence_materials``/
``record_correspondence_choice`` instead of the fixed-weight local path,
so suggestions improve from the project's learned ``SignalWeights`` the
same way the Krita Character Colors Docker's milestone-4 workflow does.
Without a bound project, correspondence assignment stays in-memory with
fixed 0.5/0.5 weights, as before. Saving a canvas document (still the
plain ``.npy``-directory format from slice 8) inside a bound project's
own directory also attaches it as a project asset
(``project.attach_editor_document``), so the project manifest tracks
which canvas documents belong to it; saving elsewhere still works, just
untracked. Once a project is bound, its already-attached documents and
style bibles populate the Project Documents/Project Bibles combos so
they can be reopened/reloaded without re-navigating a file dialog each
time -- the same convenience the Krita Character Colors Docker's own
bible dropdown gives its lesson-flow projects. A Hardness spin box
(default 1.0, a fully hard edge -- unchanged behavior from before this
option existed) switches the color brush between the original hard-edged
stamping and a soft, falloff-edged one (``editor.brush``'s
``stamp_dot_soft``/``stamp_line_soft``); mask painting always stays
hard-edged. A third Pan/Brush/Eraser radio option adds an Eraser tool
sharing the same Size/Hardness controls, reducing the active layer's
alpha (``editor.brush.erase_dot``/``erase_line``) instead of painting a
new color; mask mode ignores the Eraser selection and keeps its own
direct-overwrite mask painting either way. Propagate Correspondence
extends an existing region's correspondence onto explicit target
regions the artist lists (adjacency-suggested, never auto-applied),
mirroring the Krita Character Colors Docker's own Propagate
Correspondence action (milestone C4.1, issue #21) via
``colorization.correspondence.CorrespondenceSet.propagate`` directly --
this was the one milestone C4.1 capability the standalone editor's
correspondence slices (issues #31/#34) never brought over. Detach
Selected Document/Detach Selected Bible remove a Project Documents/
Project Bibles entry from the bound project's manifest (never the
underlying files, matching ``project.detach_editor_document``/
``detach_style_bible``'s own "detach never deletes" contract) --
``project.attach_editor_document``/``upsert_project_style_bible`` wired
attaching in slices 11/12, but nothing ever wired the reverse. Binding
or creating a project also loads its own bound correspondence set (if
any) into memory immediately -- a project has at most one correspondence
set in this editor's usage (always saved under the same fixed id), so
there is nothing to pick from a combo the way documents/bibles need;
without this, reopening an existing project silently lost its
correspondence assignments until the artist re-triggered a save via
Assign/Propagate Correspondence.

New feature, not code motion.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from colorization.correspondence import (
    CorrespondenceSet,
    load_correspondence_set,
    save_correspondence_set,
)
from colorization.style_bible import CharacterStyleBible, load_style_bible
from editor import (
    PALETTE_ROLES,
    EditHistory,
    LayerStack,
    adjacency_agreement_by_material,
    adjacent_region_ids,
    apply_palette_color_to_region,
    assign_region_correspondence,
    close_line_gaps_in_layer,
    load_document,
    rank_material_candidates,
    region_adjacency_for_regions,
    save_document,
    segment_layer_into_regions,
)
from project import (
    attach_editor_document,
    create_project,
    detach_editor_document,
    detach_style_bible,
    load_project,
    rank_correspondence_materials,
    record_correspondence_choice,
    upsert_project_correspondence_set,
    upsert_project_style_bible,
)
from project.storage import MANIFEST_NAME
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..elements.layer_canvas import LayerCanvas
from ..elements.layer_list_panel import LayerListPanel

_DEFAULT_WIDTH = 1200
_DEFAULT_HEIGHT = 1600
_DEFAULT_BRUSH_RADIUS = 4
_DEFAULT_BRUSH_HARDNESS = 1.0


class ReferenceColoringTab(QWidget):
    """Standalone canvas + layer stack editor, with a brush paint tool and
    undo/redo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: EditHistory | None = None
        self._style_bible: CharacterStyleBible | None = None
        self._correspondence_set: CorrespondenceSet | None = None
        self._region_layer_ids: list[str] = []
        self._project_directory: str | None = None
        self._bible_asset_path: str | None = None
        self._last_ranked_candidates: list[dict] | None = None
        self._status = QLabel("No canvas yet. Click New Canvas to begin.", self)
        self._status.setWordWrap(True)
        self._new_canvas_button = QPushButton("New Canvas", self)
        self._new_canvas_button.clicked.connect(self._new_canvas)
        self._save_document_button = QPushButton("Save Document", self)
        self._save_document_button.clicked.connect(self._save_document)
        self._open_document_button = QPushButton("Open Document", self)
        self._open_document_button.clicked.connect(self._open_document)
        self._new_project_button = QPushButton("New Project", self)
        self._new_project_button.clicked.connect(self._new_project)
        self._bind_project_button = QPushButton("Bind Project", self)
        self._bind_project_button.clicked.connect(self._bind_project)
        self._project_document_combo = QComboBox(self)
        self._open_project_document_button = QPushButton("Open Selected Document", self)
        self._open_project_document_button.clicked.connect(self._open_project_document)
        self._detach_project_document_button = QPushButton("Detach Selected Document", self)
        self._detach_project_document_button.clicked.connect(self._detach_project_document)
        self._project_bible_combo = QComboBox(self)
        self._load_project_bible_button = QPushButton("Load Selected Bible", self)
        self._load_project_bible_button.clicked.connect(self._load_project_bible)
        self._detach_project_bible_button = QPushButton("Detach Selected Bible", self)
        self._detach_project_bible_button.clicked.connect(self._detach_project_bible)

        self._canvas = LayerCanvas(self)
        self._layer_panel = LayerListPanel(self)
        self._layer_panel.layers_changed.connect(self._canvas.refresh)
        self._layer_panel.layers_changed.connect(self._update_status)
        self._layer_panel.layer_selected.connect(self._canvas.set_active_layer_id)

        self._pan_tool = QRadioButton("Pan", self)
        self._brush_tool = QRadioButton("Brush", self)
        self._eraser_tool = QRadioButton("Eraser", self)
        self._pan_tool.setChecked(True)
        self._pan_tool.toggled.connect(self._on_tool_toggled)
        self._brush_tool.toggled.connect(self._on_tool_toggled)
        self._eraser_tool.toggled.connect(self._on_tool_toggled)

        self._brush_color_button = QPushButton(self)
        self._brush_color = QColor(0, 0, 0)
        self._set_brush_color_button_swatch(self._brush_color)
        self._brush_color_button.clicked.connect(self._pick_brush_color)

        self._brush_radius_spin = QSpinBox(self)
        self._brush_radius_spin.setRange(0, 500)
        self._brush_radius_spin.setValue(_DEFAULT_BRUSH_RADIUS)
        self._brush_radius_spin.valueChanged.connect(self._on_brush_radius_changed)
        self._canvas.set_brush_radius(_DEFAULT_BRUSH_RADIUS)

        self._brush_hardness_spin = QDoubleSpinBox(self)
        self._brush_hardness_spin.setRange(0.0, 1.0)
        self._brush_hardness_spin.setSingleStep(0.05)
        self._brush_hardness_spin.setValue(_DEFAULT_BRUSH_HARDNESS)
        self._brush_hardness_spin.valueChanged.connect(self._canvas.set_brush_hardness)
        self._canvas.set_brush_hardness(_DEFAULT_BRUSH_HARDNESS)

        self._undo_button = QPushButton("Undo", self)
        self._redo_button = QPushButton("Redo", self)
        self._undo_button.clicked.connect(self._undo)
        self._redo_button.clicked.connect(self._redo)

        self._edit_mask_checkbox = QCheckBox("Edit Mask", self)
        self._edit_mask_checkbox.toggled.connect(self._canvas.set_mask_mode)
        self._mask_value_spin = QSpinBox(self)
        self._mask_value_spin.setRange(0, 255)
        self._mask_value_spin.setValue(255)
        self._mask_value_spin.valueChanged.connect(self._canvas.set_mask_intensity)

        self._max_gap_spin = QSpinBox(self)
        self._max_gap_spin.setRange(0, 50)
        self._max_gap_spin.setValue(2)
        self._close_gaps_button = QPushButton("Close Line Gaps", self)
        self._close_gaps_button.clicked.connect(self._close_line_gaps)

        self._min_region_area_spin = QSpinBox(self)
        self._min_region_area_spin.setRange(0, 1_000_000)
        self._segment_button = QPushButton("Segment Regions", self)
        self._segment_button.clicked.connect(self._segment_regions)

        self._bind_bible_button = QPushButton("Bind Style Bible", self)
        self._bind_bible_button.clicked.connect(self._bind_style_bible)
        self._material_combo = QComboBox(self)
        self._material_combo.currentIndexChanged.connect(self._refresh_role_combo)
        self._role_combo = QComboBox(self)
        self._apply_palette_button = QPushButton("Apply Palette Color", self)
        self._apply_palette_button.clicked.connect(self._apply_palette_color)

        self._suggest_material_button = QPushButton("Suggest Material", self)
        self._suggest_material_button.clicked.connect(self._suggest_material)
        self._assign_correspondence_button = QPushButton("Assign Correspondence", self)
        self._assign_correspondence_button.clicked.connect(self._assign_correspondence)
        self._propagate_correspondence_button = QPushButton("Propagate Correspondence", self)
        self._propagate_correspondence_button.clicked.connect(self._propagate_correspondence)

        controls = QHBoxLayout()
        controls.addWidget(self._new_canvas_button)
        controls.addWidget(self._save_document_button)
        controls.addWidget(self._open_document_button)
        controls.addWidget(self._new_project_button)
        controls.addWidget(self._bind_project_button)
        controls.addWidget(self._pan_tool)
        controls.addWidget(self._brush_tool)
        controls.addWidget(self._eraser_tool)
        controls.addWidget(QLabel("Color:", self))
        controls.addWidget(self._brush_color_button)
        controls.addWidget(QLabel("Size:", self))
        controls.addWidget(self._brush_radius_spin)
        controls.addWidget(QLabel("Hardness:", self))
        controls.addWidget(self._brush_hardness_spin)
        controls.addWidget(self._undo_button)
        controls.addWidget(self._redo_button)
        controls.addWidget(self._edit_mask_checkbox)
        controls.addWidget(QLabel("Mask value:", self))
        controls.addWidget(self._mask_value_spin)
        controls.addWidget(QLabel("Max gap:", self))
        controls.addWidget(self._max_gap_spin)
        controls.addWidget(self._close_gaps_button)
        controls.addWidget(QLabel("Min region area:", self))
        controls.addWidget(self._min_region_area_spin)
        controls.addWidget(self._segment_button)
        controls.addStretch(1)

        palette_controls = QHBoxLayout()
        palette_controls.addWidget(self._bind_bible_button)
        palette_controls.addWidget(QLabel("Material:", self))
        palette_controls.addWidget(self._material_combo)
        palette_controls.addWidget(QLabel("Role:", self))
        palette_controls.addWidget(self._role_combo)
        palette_controls.addWidget(self._apply_palette_button)
        palette_controls.addWidget(self._suggest_material_button)
        palette_controls.addWidget(self._assign_correspondence_button)
        palette_controls.addWidget(self._propagate_correspondence_button)
        palette_controls.addStretch(1)

        project_asset_controls = QHBoxLayout()
        project_asset_controls.addWidget(QLabel("Project Documents:", self))
        project_asset_controls.addWidget(self._project_document_combo)
        project_asset_controls.addWidget(self._open_project_document_button)
        project_asset_controls.addWidget(self._detach_project_document_button)
        project_asset_controls.addWidget(QLabel("Project Bibles:", self))
        project_asset_controls.addWidget(self._project_bible_combo)
        project_asset_controls.addWidget(self._load_project_bible_button)
        project_asset_controls.addWidget(self._detach_project_bible_button)
        project_asset_controls.addStretch(1)

        right = QVBoxLayout()
        right.addLayout(controls)
        right.addLayout(palette_controls)
        right.addLayout(project_asset_controls)
        right.addWidget(self._layer_panel)
        right.addWidget(self._status)

        root = QHBoxLayout(self)
        root.addWidget(self._canvas, stretch=3)
        right_container = QWidget(self)
        right_container.setLayout(right)
        root.addWidget(right_container, stretch=1)

    def _new_canvas(self) -> None:
        width, accepted = QInputDialog.getInt(
            self, "New Canvas", "Width (px):", _DEFAULT_WIDTH, 1, 16384
        )
        if not accepted:
            return
        height, accepted = QInputDialog.getInt(
            self, "New Canvas", "Height (px):", _DEFAULT_HEIGHT, 1, 16384
        )
        if not accepted:
            return
        layer_stack = LayerStack(width, height)
        layer_stack.add_layer("layer-1", "Layer 1")
        self._history = EditHistory(layer_stack)
        self._canvas.set_layer_stack(layer_stack)
        self._canvas.set_history(self._history)
        self._layer_panel.set_layer_stack(layer_stack)
        self._layer_panel.set_history(self._history)
        self._layer_panel.select_layer("layer-1")
        self._update_status()

    def _save_document(self) -> None:
        """Write the current canvas, plus any in-memory correspondence
        assignments and region-layer bookkeeping, to a chosen directory. If
        that directory sits inside a bound project, also attach it as a
        project asset (``project.attach_editor_document``) so the project
        manifest tracks it -- saving elsewhere still works, just untracked."""
        layer_stack = self._canvas.layer_stack()
        if layer_stack is None:
            return
        directory = QFileDialog.getExistingDirectory(self, "Save Document")
        if not directory:
            return
        destination = Path(directory)
        save_document(destination, layer_stack)
        if self._correspondence_set is not None:
            save_correspondence_set(destination / "correspondence.json", self._correspondence_set)
        if self._region_layer_ids:
            (destination / "region_layers.json").write_text(
                json.dumps(self._region_layer_ids), encoding="utf-8"
            )
        attached_note = ""
        if self._project_directory is not None:
            relative = self._relative_to_project(destination)
            if relative is not None:
                attach_editor_document(self._project_directory, asset_path=relative)
                attached_note = " (attached to bound project)"
                self._refresh_project_asset_combos()
        self._status.setText(f"Saved document to {directory}{attached_note}.")

    def _relative_to_project(self, path: Path) -> str | None:
        """``path`` relative to the bound project's root as a POSIX asset
        path, or ``None`` if unbound, outside the project, or the project
        root itself (an empty relative path isn't a usable asset name)."""
        if self._project_directory is None:
            return None
        project_root = Path(self._project_directory).resolve()
        try:
            relative = path.resolve().relative_to(project_root)
        except ValueError:
            return None
        return relative.as_posix() if relative.parts else None

    def _open_document(self) -> None:
        """Replace the current canvas with a document previously written by
        Save Document, resetting undo/redo history and region/correspondence
        bookkeeping to match. The bound style bible, if any, is left as-is:
        a document does not carry its own bible reference."""
        directory = QFileDialog.getExistingDirectory(self, "Open Document")
        if not directory:
            return
        self._load_document_from_path(Path(directory))

    def _open_project_document(self) -> None:
        """Reopen a document already attached to the bound project, picked
        from Project Documents, without a file dialog."""
        if self._project_directory is None or self._project_document_combo.currentIndex() < 0:
            return
        relative = self._project_document_combo.currentData()
        self._load_document_from_path(Path(self._project_directory) / relative)

    def _load_document_from_path(self, source: Path) -> None:
        try:
            layer_stack = load_document(source)
        except (OSError, ValueError) as error:
            self._status.setText(f"Could not open document: {error}")
            return
        self._history = EditHistory(layer_stack)
        self._canvas.set_layer_stack(layer_stack)
        self._canvas.set_history(self._history)
        self._layer_panel.set_layer_stack(layer_stack)
        self._layer_panel.set_history(self._history)
        layers = layer_stack.layers()
        if layers:
            self._layer_panel.select_layer(layers[0].meta.id)
        region_layers_path = source / "region_layers.json"
        self._region_layer_ids = (
            json.loads(region_layers_path.read_text(encoding="utf-8"))
            if region_layers_path.exists()
            else []
        )
        correspondence_path = source / "correspondence.json"
        self._correspondence_set = (
            load_correspondence_set(correspondence_path)
            if correspondence_path.exists()
            else None
        )
        self._update_status()

    def _new_project(self) -> None:
        """Create a bare portable ``project`` manifest (no exercise/attempt --
        that's the Krita tutor's own entry point) in a chosen empty folder,
        and bind this tab to it. A bound project's learned ``SignalWeights``
        make Suggest Material/Assign Correspondence improve over time,
        unlike the fixed-weight in-memory path used without one."""
        directory = QFileDialog.getExistingDirectory(self, "New Project (choose an empty folder)")
        if not directory:
            return
        title, accepted = QInputDialog.getText(self, "New Project", "Title:")
        if not accepted or not title.strip():
            return
        try:
            create_project(directory, title=title)
        except (OSError, ValueError) as error:
            self._status.setText(f"Could not create project: {error}")
            return
        self._project_directory = directory
        self._bible_asset_path = None
        self._refresh_project_asset_combos()
        self._status.setText(f"Created and bound project at {directory}.")

    def _bind_project(self) -> None:
        """Bind this tab to an existing project directory (one already
        created here, or by the Krita tutor's own project flow)."""
        directory = QFileDialog.getExistingDirectory(self, "Bind Project")
        if not directory:
            return
        if not (Path(directory) / MANIFEST_NAME).is_file():
            self._status.setText("Selected directory has no project manifest.")
            return
        self._project_directory = directory
        self._bible_asset_path = None
        self._refresh_project_asset_combos()
        self._status.setText(f"Bound project at {directory}.")

    def _refresh_project_asset_combos(self) -> None:
        """Repopulate Project Documents/Project Bibles from the bound
        project's current asset lists (relative path as both label and
        data), so they can be reopened/reloaded without a file dialog.
        Also loads the project's own bound correspondence set (if any)
        into memory -- unlike documents/bibles, a project has at most one
        correspondence set in this editor's usage (always saved under the
        same fixed id), so there is nothing to pick from a combo; binding
        or creating a project should just make an existing one available
        immediately, the same way Open Document already does for a
        document's own sidecar correspondence.json."""
        self._project_document_combo.clear()
        self._project_bible_combo.clear()
        self._correspondence_set = None
        if self._project_directory is None:
            return
        project = load_project(self._project_directory)
        for asset in project.editor_document_assets:
            self._project_document_combo.addItem(asset, asset)
        for asset in project.style_bible_assets:
            self._project_bible_combo.addItem(asset, asset)
        if project.correspondence_set_assets:
            asset_path = project.correspondence_set_assets[0]
            try:
                self._correspondence_set = load_correspondence_set(
                    Path(self._project_directory) / asset_path
                )
            except (OSError, ValueError):
                self._correspondence_set = None

    def _update_status(self) -> None:
        layer_stack = self._canvas.layer_stack()
        if layer_stack is None:
            self._status.setText("No canvas yet. Click New Canvas to begin.")
            return
        self._status.setText(
            f"Canvas {layer_stack.width}x{layer_stack.height}, "
            f"{len(layer_stack.layers())} layer(s)."
        )

    def _on_tool_toggled(self) -> None:
        if self._brush_tool.isChecked():
            tool = "brush"
        elif self._eraser_tool.isChecked():
            tool = "eraser"
        else:
            tool = "pan"
        self._canvas.set_tool(tool)

    def _pick_brush_color(self) -> None:
        color = QColorDialog.getColor(self._brush_color, self, "Brush Color")
        if not color.isValid():
            return
        self._brush_color = color
        self._set_brush_color_button_swatch(color)
        self._canvas.set_brush_color((color.red(), color.green(), color.blue(), color.alpha()))

    def _set_brush_color_button_swatch(self, color: QColor) -> None:
        self._brush_color_button.setStyleSheet(f"background-color: {color.name()};")
        self._canvas.set_brush_color((color.red(), color.green(), color.blue(), color.alpha()))

    def _on_brush_radius_changed(self, value: int) -> None:
        self._canvas.set_brush_radius(value)

    def _close_line_gaps(self) -> None:
        layer_stack = self._canvas.layer_stack()
        layer_id = self._layer_panel.selected_layer_id()
        if layer_stack is None or layer_id is None:
            return
        if self._history is not None:
            self._history.record()
        if close_line_gaps_in_layer(layer_stack, layer_id, self._max_gap_spin.value()):
            self._canvas.refresh()

    def _segment_regions(self) -> None:
        layer_stack = self._canvas.layer_stack()
        layer_id = self._layer_panel.selected_layer_id()
        if layer_stack is None or layer_id is None:
            return
        if self._history is not None:
            self._history.record()
        new_ids = segment_layer_into_regions(
            layer_stack, layer_id, min_region_area=self._min_region_area_spin.value()
        )
        if new_ids:
            self._region_layer_ids.extend(new_ids)
            self._layer_panel.refresh()
            self._canvas.refresh()
            self._update_status()

    def _bind_style_bible(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, "Bind Style Bible", "", "Style Bible (*.json)"
        )
        if not path:
            return
        try:
            bible = load_style_bible(path)
        except (OSError, ValueError):
            return
        self._apply_loaded_style_bible(bible)
        if self._project_directory is not None:
            try:
                self._bible_asset_path = upsert_project_style_bible(
                    self._project_directory, payload=bible.to_dict()
                )
                self._refresh_project_asset_combos()
            except (OSError, ValueError) as error:
                self._status.setText(f"Could not attach bible to project: {error}")

    def _load_project_bible(self) -> None:
        """Load a style bible already attached to the bound project, picked
        from Project Bibles, without a file dialog."""
        if self._project_directory is None or self._project_bible_combo.currentIndex() < 0:
            return
        relative = self._project_bible_combo.currentData()
        try:
            bible = load_style_bible(Path(self._project_directory) / relative)
        except (OSError, ValueError) as error:
            self._status.setText(f"Could not load bible: {error}")
            return
        self._apply_loaded_style_bible(bible)
        self._bible_asset_path = relative

    def _detach_project_document(self) -> None:
        """Remove the selected Project Documents entry from the bound
        project's manifest; the document directory and its files are
        never deleted, matching ``project.detach_editor_document``."""
        if self._project_directory is None or self._project_document_combo.currentIndex() < 0:
            return
        relative = self._project_document_combo.currentData()
        detach_editor_document(self._project_directory, asset_path=relative)
        self._refresh_project_asset_combos()
        self._status.setText(f"Detached document '{relative}' from the bound project.")

    def _detach_project_bible(self) -> None:
        """Remove the selected Project Bibles entry from the bound
        project's manifest; the bible file is never deleted, matching
        ``project.detach_style_bible``. If the detached bible is the one
        currently loaded, ``Suggest Material`` falls back to the
        fixed-weight local ranking (no attached bible left to look up
        the project's learned ``SignalWeights`` against)."""
        if self._project_directory is None or self._project_bible_combo.currentIndex() < 0:
            return
        relative = self._project_bible_combo.currentData()
        detach_style_bible(self._project_directory, asset_path=relative)
        if self._bible_asset_path == relative:
            self._bible_asset_path = None
        self._refresh_project_asset_combos()
        self._status.setText(f"Detached bible '{relative}' from the bound project.")

    def _apply_loaded_style_bible(self, bible: CharacterStyleBible) -> None:
        self._style_bible = bible
        self._bible_asset_path = None
        self._material_combo.clear()
        for material in bible.materials:
            self._material_combo.addItem(material.label, material.id)
        self._refresh_role_combo()

    def _refresh_role_combo(self) -> None:
        self._role_combo.clear()
        material = self._selected_material()
        if material is None:
            return
        for role in PALETTE_ROLES:
            if role != "accent" or material.palette.accent is not None:
                self._role_combo.addItem(role)

    def _selected_material(self):
        if self._style_bible is None or self._material_combo.currentIndex() < 0:
            return None
        material_id = self._material_combo.currentData()
        return next((item for item in self._style_bible.materials if item.id == material_id), None)

    def _apply_palette_color(self) -> None:
        layer_stack = self._canvas.layer_stack()
        layer_id = self._layer_panel.selected_layer_id()
        material = self._selected_material()
        role = self._role_combo.currentText()
        if layer_stack is None or layer_id is None or material is None or not role:
            return
        if self._history is not None:
            self._history.record()
        if apply_palette_color_to_region(layer_stack, layer_id, material.palette, role):
            self._canvas.refresh()

    def _suggest_material(self) -> None:
        """Rank the bound bible's materials for the selected region layer and
        select the top candidate in the Material combo, without assigning
        anything -- the artist still confirms via Apply Palette Color and/or
        Assign Correspondence. When a project is bound with this bible
        attached, ranking uses the project's learned ``SignalWeights``
        (``project.rank_correspondence_materials``) instead of the fixed
        0.5/0.5 local weights, and the candidates are kept so a following
        Assign Correspondence can report the choice back for correction
        learning."""
        layer_stack = self._canvas.layer_stack()
        layer_id = self._layer_panel.selected_layer_id()
        if layer_stack is None or layer_id is None or self._style_bible is None:
            return
        pairs = region_adjacency_for_regions(layer_stack, self._region_layer_ids)
        correspondence_set = self._correspondence_set or self._empty_correspondence_set()
        agreements = adjacency_agreement_by_material(layer_id, pairs, correspondence_set)
        if self._project_directory is not None and self._bible_asset_path is not None:
            ranked = rank_correspondence_materials(
                self._project_directory,
                bible_asset_path=self._bible_asset_path,
                region_id=layer_id,
                adjacency_agreements=agreements,
            )
        else:
            ranked = rank_material_candidates(layer_id, self._style_bible, agreements)
        self._last_ranked_candidates = ranked or None
        if not ranked:
            return
        top = ranked[0]
        index = self._material_combo.findData(top["material_id"])
        if index >= 0:
            self._material_combo.setCurrentIndex(index)
        self._status.setText(
            f"Suggested '{top['material_id']}' for '{layer_id}' "
            f"(confidence {top['confidence']:.2f})."
        )

    def _assign_correspondence(self) -> None:
        """Record the currently selected Material/Role as this region's
        correspondence, so future ``_suggest_material`` calls can use it as
        an adjacency signal for neighboring regions. Never recolors
        anything itself -- use Apply Palette Color for that. When a
        project is bound, the updated correspondence set is also persisted
        into it, and -- if Suggest Material was called first for this
        region -- the choice is reported to
        ``project.record_correspondence_choice`` so the project's
        ``SignalWeights`` learn from it."""
        layer_id = self._layer_panel.selected_layer_id()
        material = self._selected_material()
        role = self._role_combo.currentText()
        if layer_id is None or material is None or not role or self._style_bible is None:
            return
        correspondence_set = self._correspondence_set or self._empty_correspondence_set()
        try:
            updated = assign_region_correspondence(
                correspondence_set,
                region_id=layer_id,
                material_id=material.id,
                role=role,
                new_id="correspondence-" + uuid.uuid4().hex[:8],
            )
        except ValueError as error:
            self._status.setText(str(error))
            return
        self._correspondence_set = updated
        if self._project_directory is not None:
            upsert_project_correspondence_set(self._project_directory, payload=updated.to_dict())
            if self._last_ranked_candidates:
                record_correspondence_choice(
                    self._project_directory,
                    chosen_material_id=material.id,
                    candidates=self._last_ranked_candidates,
                )
        self._last_ranked_candidates = None
        self._status.setText(f"Assigned region '{layer_id}' to {material.id}/{role}.")

    def _propagate_correspondence(self) -> None:
        """Extend the selected region's existing correspondence onto
        explicit target regions, mirroring the Krita Character Colors
        Docker's Propagate Correspondence action (milestone C4.1, issue
        #21). Adjacency suggests targets (pre-filling the prompt) but
        never auto-applies -- only regions the artist explicitly lists
        (and confirms) are ever assigned. Never recolors anything itself."""
        layer_stack = self._canvas.layer_stack()
        source_region_id = self._layer_panel.selected_layer_id()
        if layer_stack is None or source_region_id is None or self._correspondence_set is None:
            return
        source = next(
            (
                item
                for item in self._correspondence_set.correspondences
                if item.region_id == source_region_id
            ),
            None,
        )
        if source is None:
            self._status.setText(
                f"'{source_region_id}' has no existing correspondence to propagate."
            )
            return
        pairs = region_adjacency_for_regions(layer_stack, self._region_layer_ids)
        suggested = sorted(adjacent_region_ids(source_region_id, pairs))
        targets_text, accepted = QInputDialog.getText(
            self,
            "Propagate Correspondence",
            "Comma-separated target region ids (adjacency-suggested; edit as needed):",
            text=", ".join(suggested),
        )
        if not accepted:
            return
        target_region_ids = [item.strip() for item in targets_text.split(",") if item.strip()]
        if not target_region_ids:
            self._status.setText("Enter at least one explicit target region id.")
            return
        try:
            propagated = self._correspondence_set.propagate(
                source.id, target_region_ids, lambda: "correspondence-" + uuid.uuid4().hex[:8]
            )
        except ValueError as error:
            self._status.setText(str(error))
            return
        self._correspondence_set = propagated
        if self._project_directory is not None:
            upsert_project_correspondence_set(self._project_directory, payload=propagated.to_dict())
        self._status.setText(
            f"Propagated to {len(target_region_ids)} region(s); set now has "
            f"{len(propagated.correspondences)} correspondence(s)."
        )

    def _empty_correspondence_set(self) -> CorrespondenceSet:
        assert self._style_bible is not None
        return CorrespondenceSet(
            id="editor-correspondence", style_bible_id=self._style_bible.id
        )

    def correspondence_set(self) -> CorrespondenceSet | None:
        return self._correspondence_set

    def project_directory(self) -> str | None:
        return self._project_directory

    def _undo(self) -> None:
        if self._history is None or not self._history.undo():
            return
        self._canvas.refresh()
        self._layer_panel.refresh()
        self._update_status()

    def _redo(self) -> None:
        if self._history is None or not self._history.redo():
            return
        self._canvas.refresh()
        self._layer_panel.refresh()
        self._update_status()

    def canvas(self) -> LayerCanvas:
        return self._canvas

    def layer_panel(self) -> LayerListPanel:
        return self._layer_panel

    def history(self) -> EditHistory | None:
        return self._history

    def style_bible(self) -> CharacterStyleBible | None:
        return self._style_bible


__all__ = ["ReferenceColoringTab"]
