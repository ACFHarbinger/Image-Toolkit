"""Reusable Recent Directories Picker and Dropdown Menu component (§2.5, §2.21D)."""

from __future__ import annotations

import os
from typing import Callable, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QToolButton, QWidget

from gui.src.windows.settings.app_settings import AppSettings


class RecentDirectoriesPicker(QToolButton):
    """Dropdown tool button displaying recent directories for a gallery or tool tab."""

    directory_selected = Signal(str)

    def __init__(
        self,
        class_name: str,
        parent: Optional[QWidget] = None,
        on_directory_selected: Optional[Callable[[str], None]] = None,
        button_text: str = "🕒▾",
        max_entries: int = 10,
    ) -> None:
        super().__init__(parent)
        self.class_name = class_name
        self.max_entries = max_entries
        self._on_selected_cb = on_directory_selected

        self.setText(button_text)
        self.setToolTip("Recently Browsed Directories (GUI/UX §2.5)")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setStyleSheet(
            "QToolButton { padding: 4px 8px; font-weight: bold; border-radius: 4px; }"
            "QToolButton::menu-indicator { image: none; }"
        )

        self._menu = QMenu(self)
        self.setMenu(self._menu)
        self._menu.aboutToShow.connect(self.refresh_menu)
        self.refresh_menu()

    def get_recent_dirs(self) -> list[str]:
        """Fetch MRU directory list for the configured class."""
        dirs = AppSettings.session(self.class_name, "recent_dirs", []) or []
        if isinstance(dirs, str):
            dirs = [dirs]
        return [str(d) for d in dirs if d and os.path.exists(d)]

    def add_recent_dir(self, path: str) -> None:
        """Add path to MRU list and persist."""
        if not path or not os.path.isdir(path):
            return
        dirs = self.get_recent_dirs()
        if path in dirs:
            dirs.remove(path)
        dirs.insert(0, path)
        AppSettings.set_session(self.class_name, "recent_dirs", dirs[: self.max_entries])
        AppSettings.set_session(self.class_name, "last_dir", path)
        self.refresh_menu()

    def clear_recent_dirs(self) -> None:
        """Clear the MRU directory list for this class."""
        AppSettings.set_session(self.class_name, "recent_dirs", [])
        self.refresh_menu()

    def refresh_menu(self) -> None:
        """Populate the dropdown menu with recent directories."""
        self._menu.clear()
        dirs = self.get_recent_dirs()

        if not dirs:
            empty_act = self._menu.addAction("(No recent directories)")
            empty_act.setEnabled(False)
            return

        for d in dirs[: self.max_entries]:
            display_text = d
            # Elide long paths for cleaner menu display
            if len(display_text) > 48:
                display_text = "..." + display_text[-45:]

            act = self._menu.addAction(f"📁 {display_text}")
            act.setToolTip(d)
            act.triggered.connect(lambda _=False, p=d: self._handle_selection(p))

        self._menu.addSeparator()
        clear_act = self._menu.addAction("🗑️ Clear Recent Directories")
        clear_act.triggered.connect(self.clear_recent_dirs)

    def _handle_selection(self, path: str) -> None:
        self.directory_selected.emit(path)
        if self._on_selected_cb is not None:
            self._on_selected_cb(path)


__all__ = ["RecentDirectoriesPicker"]
