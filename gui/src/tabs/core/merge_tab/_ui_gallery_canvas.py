"""Gallery/canvas/queue/action-buttons UI section builder for ``MergeTab``.

Extracted from ``MergeTab.__init__`` -- pure code motion, no logic change
(see ``_ui_config.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QWidget,
)

from gui.src.components.containers.merge_canvas import MergeCanvas

from ....components import VirtualGallery
from ....styles import apply_shadow_effect, set_button_role


class _UIGalleryCanvasMixin:
    """Builds the image-library gallery, merge canvas, queue gallery, and action buttons."""

    def _build_gallery_section(self, content_layout) -> None:
        # === 4. Image Library Gallery (virtual-scroll, GUI/UX §2.1 Option A) ===
        self.selection_label = QLabel("0 images selected.")
        self.selection_label.setStyleSheet("padding: 4px 0; font-weight: bold;")
        content_layout.addWidget(self.selection_label)

        gallery_header = QLabel("Image Library")
        gallery_header.setStyleSheet("font-weight: bold; padding: 4px;")
        content_layout.addWidget(gallery_header)
        content_layout.addWidget(self.search_input)

        self.gallery = VirtualGallery(self)
        # Taller floor than the wallpaper gallery's matching 600: this tab's
        # page has far more sections below it (merge settings, canvas, queue,
        # action buttons), so its total content height already exceeds the
        # viewport and the layout stretch factor below never gets slack to
        # hand the gallery -- it sits at this floor by default rather than
        # growing into leftover space the way the wallpaper gallery's does.
        # ~4 rows at the default 180px thumbnail size, matching that gallery.
        self.gallery.setMinimumHeight(900)
        # MultiSelection keeps the tab's click-to-toggle interaction with
        # native highlight, while the canvas/queue remain the authoritative
        # merge-order surface (selection_changed -> _sync_selection_from_gallery).
        self.gallery.view.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self.gallery.selection_changed.connect(self._sync_selection_from_gallery)
        self.gallery.path_activated.connect(self.handle_full_image_preview)
        self.gallery.path_right_clicked.connect(self.show_image_context_menu)
        content_layout.addWidget(self.gallery, 1)

    def _build_canvas_section(self, content_layout) -> None:
        # === 5. Merge Canvas (canvas mode) / Selected Image Queue (every other mode) ===
        self.canvas_header_widget = QWidget()
        canvas_header_row = QHBoxLayout(self.canvas_header_widget)
        canvas_header_row.setContentsMargins(0, 0, 0, 0)
        canvas_lbl = QLabel("Merge Canvas")
        canvas_lbl.setStyleSheet("font-weight: bold; padding: 4px;")
        canvas_header_row.addWidget(canvas_lbl)
        canvas_header_row.addStretch()
        canvas_header_row.addWidget(QLabel("W:"))
        self.canvas_w_spin = QSpinBox()
        self.canvas_w_spin.setRange(100, 20000)
        self.canvas_w_spin.setValue(1920)
        self.canvas_w_spin.setSingleStep(10)
        self.canvas_w_spin.setFixedWidth(75)
        canvas_header_row.addWidget(self.canvas_w_spin)
        canvas_header_row.addWidget(QLabel("H:"))
        self.canvas_h_spin = QSpinBox()
        self.canvas_h_spin.setRange(100, 20000)
        self.canvas_h_spin.setValue(1080)
        self.canvas_h_spin.setSingleStep(10)
        self.canvas_h_spin.setFixedWidth(75)
        canvas_header_row.addWidget(self.canvas_h_spin)
        canvas_header_row.addWidget(QLabel("BG:"))
        self.canvas_bg_combo = QComboBox()
        self.canvas_bg_combo.addItems(["Transparent", "White", "Black"])
        canvas_header_row.addWidget(self.canvas_bg_combo)
        content_layout.addWidget(self.canvas_header_widget)

        self.canvas_widget = MergeCanvas(1920, 1080)
        self.canvas_widget.setMinimumHeight(600)
        self.canvas_widget.item_selected.connect(self._on_canvas_item_selected)
        content_layout.addWidget(self.canvas_widget, 1)

        # Per-item controls (x, y, w, h + remove/clear buttons) — canvas mode only.
        self.item_ctrl_widget = QWidget()
        item_ctrl_layout = QHBoxLayout(self.item_ctrl_widget)
        item_ctrl_layout.setContentsMargins(0, 2, 0, 2)
        self.spin_list = []
        for attr, label_txt, lo, hi in (
            ("item_x_spin", "X:", -20000, 20000),
            ("item_y_spin", "Y:", -20000, 20000),
            ("item_w_spin", "W:", 1, 20000),
            ("item_h_spin", "H:", 1, 20000),
        ):
            item_ctrl_layout.addWidget(QLabel(label_txt))
            spin = QSpinBox()
            spin.setRange(lo, hi)
            spin.setFixedWidth(72)
            spin.setEnabled(False)
            setattr(self, attr, spin)
            item_ctrl_layout.addWidget(spin)
            self.spin_list.append(spin)

        item_ctrl_layout.addStretch()

        self.btn_remove_from_canvas = QPushButton("Remove Selected")
        self.btn_remove_from_canvas.setEnabled(False)
        self.btn_remove_from_canvas.clicked.connect(self._remove_from_canvas)
        item_ctrl_layout.addWidget(self.btn_remove_from_canvas)

        self.btn_clear_canvas = QPushButton("Clear Canvas")
        self.btn_clear_canvas.clicked.connect(self._clear_canvas)
        item_ctrl_layout.addWidget(self.btn_clear_canvas)

        content_layout.addWidget(self.item_ctrl_widget)

        # Ordered thumbnail strip shown instead of the canvas for every mode
        # except "canvas" -- a draggable/reorderable view of the current
        # selection queue (order = order added, or manually dragged), with a
        # right-click menu (preview/deselect/delete) on each thumbnail.
        self.queue_header_label = QLabel("Selected Images (Merge Order)")
        self.queue_header_label.setStyleSheet("font-weight: bold; padding: 4px;")
        content_layout.addWidget(self.queue_header_label)
        self.queue_gallery_scroll = QScrollArea()
        self.queue_gallery_scroll.setWidgetResizable(True)
        self.queue_gallery_scroll.setMinimumHeight(600)
        queue_gallery_inner = QWidget()
        self.queue_gallery_layout = QGridLayout(queue_gallery_inner)
        self.queue_gallery_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.queue_gallery_scroll.setWidget(queue_gallery_inner)
        content_layout.addWidget(self.queue_gallery_scroll, 1)
        self._queue_gallery_cols = 6
        self._queue_thumb_size = 120

    def _build_action_buttons_section(self, content_layout) -> None:
        # === 6. Action Buttons ===
        btns_layout = QHBoxLayout()

        self.run_button = QPushButton("Run Merge")
        set_button_role(self.run_button, "success")
        apply_shadow_effect(self.run_button, "#000000", 8, 0, 3)
        self.run_button.clicked.connect(self.start_merge)

        self.cancel_button = QPushButton("Cancel")
        set_button_role(self.cancel_button, "danger")
        apply_shadow_effect(self.cancel_button, "#000000", 8, 0, 3)
        self.cancel_button.clicked.connect(self.cancel_merge)
        self.cancel_button.setVisible(False)

        btns_layout.addWidget(self.run_button)
        btns_layout.addWidget(self.cancel_button)
        content_layout.addLayout(btns_layout)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #b9bbbe; font-style: italic; padding: 10px;"
        )
        content_layout.addWidget(self.status_label)


__all__ = ["_UIGalleryCanvasMixin"]
