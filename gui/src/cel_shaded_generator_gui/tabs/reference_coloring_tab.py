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
Docker uses), and bind a portable style bible (``colorization.style_bible``,
reused the same way) to recolor a region layer with one of its materials'
palette roles. No correspondence-assignment/adjacency-suggestion UI yet --
that is a later slice built on top of this same
``editor.LayerStack``/``LayerCanvas``/``LayerListPanel``/``editor.brush``/
``editor.EditHistory``/``editor.segmentation_tools``/``editor.palette_tools``
foundation, mirroring how the Krita Dockers built on Krita's own layer
model.

New feature, not code motion.
"""

from __future__ import annotations

from colorization.style_bible import CharacterStyleBible, load_style_bible
from editor import (
    PALETTE_ROLES,
    EditHistory,
    LayerStack,
    apply_palette_color_to_region,
    close_line_gaps_in_layer,
    segment_layer_into_regions,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
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


class ReferenceColoringTab(QWidget):
    """Standalone canvas + layer stack editor, with a brush paint tool and
    undo/redo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: EditHistory | None = None
        self._style_bible: CharacterStyleBible | None = None
        self._status = QLabel("No canvas yet. Click New Canvas to begin.", self)
        self._status.setWordWrap(True)
        self._new_canvas_button = QPushButton("New Canvas", self)
        self._new_canvas_button.clicked.connect(self._new_canvas)

        self._canvas = LayerCanvas(self)
        self._layer_panel = LayerListPanel(self)
        self._layer_panel.layers_changed.connect(self._canvas.refresh)
        self._layer_panel.layers_changed.connect(self._update_status)
        self._layer_panel.layer_selected.connect(self._canvas.set_active_layer_id)

        self._pan_tool = QRadioButton("Pan", self)
        self._brush_tool = QRadioButton("Brush", self)
        self._pan_tool.setChecked(True)
        self._pan_tool.toggled.connect(self._on_tool_toggled)
        self._brush_tool.toggled.connect(self._on_tool_toggled)

        self._brush_color_button = QPushButton(self)
        self._brush_color = QColor(0, 0, 0)
        self._set_brush_color_button_swatch(self._brush_color)
        self._brush_color_button.clicked.connect(self._pick_brush_color)

        self._brush_radius_spin = QSpinBox(self)
        self._brush_radius_spin.setRange(0, 500)
        self._brush_radius_spin.setValue(_DEFAULT_BRUSH_RADIUS)
        self._brush_radius_spin.valueChanged.connect(self._on_brush_radius_changed)
        self._canvas.set_brush_radius(_DEFAULT_BRUSH_RADIUS)

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

        controls = QHBoxLayout()
        controls.addWidget(self._new_canvas_button)
        controls.addWidget(self._pan_tool)
        controls.addWidget(self._brush_tool)
        controls.addWidget(QLabel("Color:", self))
        controls.addWidget(self._brush_color_button)
        controls.addWidget(QLabel("Size:", self))
        controls.addWidget(self._brush_radius_spin)
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
        palette_controls.addStretch(1)

        right = QVBoxLayout()
        right.addLayout(controls)
        right.addLayout(palette_controls)
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
        self._canvas.set_tool("brush" if self._brush_tool.isChecked() else "pan")

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
            self._style_bible = load_style_bible(path)
        except (OSError, ValueError):
            self._style_bible = None
            return
        self._material_combo.clear()
        for material in self._style_bible.materials:
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
