"""Ctrl+Shift+F global cross-tab file search popup (§2.28).

Mirrors ``_tab_search.py``'s Ctrl+T popup shape (frameless QDialog, a
QLineEdit filter over a QListWidget), but searches file paths already
loaded in every instantiated gallery-like tab instead of tab names.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from gui.src.constants.windows import _MAX_RESULTS, _NESTED_GALLERY_ATTRS

# ConvertTab is a plain QWidget composing three gallery subtabs rather than
# being (or delegating to, like ExtractorTab's __getattr__) a gallery base
# itself -- these are the attribute names to look under one level down.

# Cap results so a huge library doesn't build an unbounded popup list.


class _GlobalSearchMixin:
    """Search across every loaded gallery tab's file paths and jump to a hit."""

    def _iter_gallery_tabs(self):
        """Yield (category, tab_name, gallery_widget) for every tab (or
        nested subtab) that exposes a master path list."""
        for category, tabs_in_cat in self.all_tabs.items():
            for tab_name, tab_widget in tabs_in_cat.items():
                if hasattr(tab_widget, "master_found_files") or hasattr(
                    tab_widget, "master_image_paths"
                ):
                    yield category, tab_name, tab_widget
                    continue
                for attr in _NESTED_GALLERY_ATTRS:
                    nested = getattr(tab_widget, attr, None)
                    if nested is not None and (
                        hasattr(nested, "master_found_files")
                        or hasattr(nested, "master_image_paths")
                    ):
                        yield category, tab_name, nested

    def _open_global_search(self) -> None:
        """Show the Ctrl+Shift+F floating file-search popup (§2.28)."""
        all_entries: list[tuple[str, str, str, object]] = []
        for category, tab_name, gallery in self._iter_gallery_tabs():
            paths = getattr(gallery, "master_found_files", None) or getattr(
                gallery, "master_image_paths", None
            )
            for path in paths or []:
                all_entries.append((category, tab_name, path, gallery))

        dlg = QDialog(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        dlg.setWindowTitle("Search All Tabs")
        dlg.setFixedWidth(520)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Type to search files across every loaded tab…")
        layout.addWidget(search_input)

        list_widget = QListWidget()
        list_widget.setMaximumHeight(320)
        layout.addWidget(list_widget)

        def _populate(text: str) -> None:
            list_widget.clear()
            q = text.strip().lower()
            if not q:
                return
            shown = 0
            for category, tab_name, path, gallery in all_entries:
                if q in os.path.basename(path).lower() or q in path.lower():
                    label = f"{os.path.basename(path)}  —  {tab_name} ({category})"
                    item = QListWidgetItem(label)
                    item.setToolTip(path)
                    item.setData(Qt.ItemDataRole.UserRole, (category, tab_name, path, gallery))
                    list_widget.addItem(item)
                    shown += 1
                    if shown >= _MAX_RESULTS:
                        break
            if list_widget.count():
                list_widget.setCurrentRow(0)

        def _activate(item=None) -> None:
            if item is None:
                item = list_widget.currentItem()
            if item is None:
                return
            category, tab_name, path, gallery = item.data(Qt.ItemDataRole.UserRole)
            self.command_combo.setCurrentText(category)
            QTimer.singleShot(0, lambda: self._select_tab_by_name(tab_name))
            QTimer.singleShot(0, lambda: gallery.jump_to_path(path))
            dlg.accept()

        search_input.textChanged.connect(_populate)
        search_input.returnPressed.connect(_activate)
        list_widget.itemActivated.connect(_activate)
        list_widget.itemDoubleClicked.connect(_activate)

        dlg.exec()


__all__ = ["_GlobalSearchMixin"]
