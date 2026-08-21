"""Widget construction for ``MonitorDropView`` (``_build_ui``).

Extracted from ``monitor_drop_view.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout


class _UIBuilderMixin:
    """Builds the top/bottom info labels and applies the default drop-target style."""

    def _build_ui(self) -> None:
        self.drag_start_position = None
        self.other_monitors: list[tuple[str, str]] = []  # Added for multi-monitor swap

        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._handle_single_click)

        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)

        # Dynamic size based on display orientation (landscape vs portrait)
        width, height = self.get_resolved_dimensions()
        if height > width:
            self.setFixedSize(160, 220)
        else:
            self.setFixedSize(220, 160)

        # Setup child labels for top monitor port and bottom real full name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.top_label = QLabel(self)
        self.top_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.top_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                background-color: rgba(14, 18, 24, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)

        self.bottom_label = QLabel(self)
        self.bottom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bottom_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                font-size: 10px;
                background-color: rgba(14, 18, 24, 0.55);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)

        layout.addWidget(self.top_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addStretch(1)
        layout.addWidget(self.bottom_label, 0, Qt.AlignmentFlag.AlignBottom)

        self.update_text()
        self.default_style = """
            QLabel {
                background-color: rgba(20, 24, 32, 0.35);
                border: 2px dashed rgba(255, 255, 255, 0.20);
                border-radius: 8px;
                color: #b9bbbe;
                font-size: 14px;
            }
            QLabel[dragging="true"] {
                border: 2px solid #5865f2;
                background-color: rgba(64, 68, 75, 0.65);
            }
        """
        self.setStyleSheet(self.default_style)


__all__ = ["_UIBuilderMixin"]
