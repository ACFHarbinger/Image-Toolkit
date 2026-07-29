"""Gallery/canvas/queue/action-buttons UI section builder for ``MergeTab``.

Extracted from ``MergeTab.__init__`` -- pure code motion, no logic change
(see ``_ui_config.py``'s docstring).
"""

from __future__ import annotations

from gui.src.components.containers.merge_canvas import MergeCanvas
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QWidget,
)

from ....components import MarqueeScrollArea
from ....styles import SHARED_BUTTON_STYLE, apply_shadow_effect


class _UIGalleryCanvasMixin:
    """Builds the image-library gallery, merge canvas, queue gallery, and action buttons."""

    def _build_gallery_section(self, content_layout) -> None:
        # === 4. Image Library Gallery ===
        self.selection_label = QLabel("0 images selected.")
        self.selection_label.setStyleSheet("padding: 4px 0; font-weight: bold;")
        content_layout.addWidget(self.selection_label)

        gallery_header = QLabel("Image Library")
        gallery_header.setStyleSheet("font-weight: bold; padding: 4px;")
        content_layout.addWidget(gallery_header)
        content_layout.addWidget(self.search_input)

        self.gallery_scroll_area = MarqueeScrollArea()
        self.gallery_scroll_area.setWidgetResizable(True)  # pyrefly: ignore [missing-attribute]
        self.gallery_scroll_area.setStyleSheet(  # pyrefly: ignore [missing-attribute]
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.gallery_scroll_area.setMinimumHeight(600)  # pyrefly: ignore [missing-attribute]

        gallery_inner = QWidget()
        gallery_inner.setStyleSheet("background-color: #2c2f33;")
        self.gallery_layout = QGridLayout(gallery_inner)
        self.gallery_layout.setAlignment(  # pyrefly: ignore [missing-attribute]
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.gallery_scroll_area.setWidget(gallery_inner)  # pyrefly: ignore [missing-attribute]

        content_layout.addWidget(self.gallery_scroll_area, 1)  # pyrefly: ignore [bad-argument-type]
        content_layout.addWidget(
            self.pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
        )

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

        # Read-only ordered thumbnail strip shown instead of the canvas for
        # every mode except "canvas" — a passive view of the current
        # selection queue (order = order added), with no drag/resize.
        self.queue_header_label = QLabel("Selected Images (Merge Order)")
        self.queue_header_label.setStyleSheet("font-weight: bold; padding: 4px;")
        content_layout.addWidget(self.queue_header_label)
        self.queue_gallery_scroll = QScrollArea()
        self.queue_gallery_scroll.setWidgetResizable(True)
        self.queue_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.queue_gallery_scroll.setMinimumHeight(600)
        queue_gallery_inner = QWidget()
        queue_gallery_inner.setStyleSheet("background-color: #2c2f33;")
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
        self.run_button.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.run_button, "#000000", 8, 0, 3)
        self.run_button.clicked.connect(self.start_merge)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; font-weight: bold; "
            "padding: 12px; border-radius: 8px; }"
            "QPushButton:hover { background-color: #e74c3c; }"
        )
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
