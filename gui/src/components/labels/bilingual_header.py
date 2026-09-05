"""Bilingual micro-typography header component for Anime Creative Suite (§2.37, #505)."""

from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class BilingualHeader(QWidget):
    """Header widget featuring English title paired with Japanese micro-typography subtext."""

    def __init__(
        self,
        title: str,
        japanese_subtext: Optional[str] = None,
        level: int = 1,
        show_accent_bar: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._japanese_subtext = japanese_subtext
        self._level = level
        self._show_accent_bar = show_accent_bar
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("bilingual_header")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        # Accent Bar indicator
        if self._show_accent_bar:
            self.accent_bar = QFrame()
            self.accent_bar.setFixedWidth(3)
            self.accent_bar.setStyleSheet("background-color: #00f0ff; border-radius: 1.5px;")
            layout.addWidget(self.accent_bar)

        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        # Main Title
        font_size = "14pt" if self._level == 1 else "11pt" if self._level == 2 else "9.5pt"
        self.title_label = QLabel(self._title)
        self.title_label.setObjectName("header_title")
        self.title_label.setStyleSheet(f"font-weight: 700; font-size: {font_size}; letter-spacing: 0.5px;")
        text_layout.addWidget(self.title_label)

        # Japanese Micro-Typography Subtext
        if self._japanese_subtext:
            self.sub_label = QLabel(f"// {self._japanese_subtext}")
            self.sub_label.setObjectName("header_japanese_subtext")
            self.sub_label.setStyleSheet("color: #71717a; font-size: 8pt; font-weight: 500; font-family: 'Inter', 'Segoe UI', sans-serif;")
            text_layout.addWidget(self.sub_label)
        else:
            self.sub_label = None

        layout.addWidget(text_container, 1)

    def set_text(self, title: str, japanese_subtext: Optional[str] = None) -> None:
        self._title = title
        self._japanese_subtext = japanese_subtext
        self.title_label.setText(title)
        if self.sub_label:
            if japanese_subtext:
                self.sub_label.setText(f"// {japanese_subtext}")
                self.sub_label.show()
            else:
                self.sub_label.hide()


__all__ = ["BilingualHeader"]
