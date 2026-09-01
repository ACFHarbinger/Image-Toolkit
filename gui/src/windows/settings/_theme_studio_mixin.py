"""Appearance and Themes settings tab: Theme Studio + QSS editor (#438/#441).

Builds a new settings tab hosting the ThemeStudioPanel (semantic palette,
WCAG advisories, corners, typography, density axis, transactional preview)
and the QssEditorWidget (expert raw-QSS override). The studio's apply
callback routes through the main window's apply_theme_pack (hybrid bridge
onto the existing $VAR QSS system).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.src.theming.schema import ThemePack
from gui.src.theming.theme_studio import ThemeStudioPanel
from gui.src.theming.theme_tools import QssEditorWidget, export_theme_pack


class _ThemeStudioMixin:
    """Builds the Appearance and Themes tab and its apply/export plumbing."""

    def _build_theme_studio_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Start from the current shipped defaults: base + resolved defaults.
        pack = ThemePack(name="custom", base=self.initial_theme or "dark")

        # Active theme pack (persisted later; in-memory for this session).
        self.theme_pack = pack

        self.theme_studio = ThemeStudioPanel(
            pack,
            apply_callback=self._apply_theme_pack_cb,
        )
        layout.addWidget(self.theme_studio)

        # Export row (cross-surface theme pack, #441).
        export_row = QHBoxLayout()
        export_row.addWidget(QLabel("Portable theme pack:"))
        self.export_theme_button = QPushButton("Export theme pack…")
        self.export_theme_button.clicked.connect(self._export_current_theme)
        export_row.addWidget(self.export_theme_button)
        export_row.addStretch()
        layout.addLayout(export_row)

        # Expert QSS editor (behind the unrestricted toggle).
        qss_group = QGroupBox("Expert: raw QSS override")
        qss_layout = QVBoxLayout(qss_group)
        self.qss_editor = QssEditorWidget()
        self.qss_editor.load_from_disk()
        qss_layout.addWidget(self.qss_editor)
        layout.addWidget(qss_group)

        layout.addStretch()
        return tab

    def _apply_theme_pack_cb(self, pack: ThemePack) -> None:
        """Live-apply a candidate pack via the main window's theme mixin."""
        self.theme_pack = pack
        if self.main_window_ref is not None and hasattr(
            self.main_window_ref, "apply_theme_pack"
        ):
            self.main_window_ref.apply_theme_pack(pack)

    def _export_current_theme(self) -> None:
        dest, _selected = QFileDialog.getSaveFileName(
            self, "Export Theme Pack", "", "Theme pack (*.json)"
        )
        if not dest:
            return
        try:
            export_theme_pack(self.theme_pack, dest)
        except Exception as exc:  # pragma: no cover - dialog error path
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "Export failed", str(exc))
            return
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, "Exported", f"Theme pack written to {dest}")


__all__ = ["_ThemeStudioMixin"]
