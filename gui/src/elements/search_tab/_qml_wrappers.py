"""QML-facing search wrappers and result-display/clear helpers.

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Qt

from ...utils.sort_utils import natural_sort_key


class _QmlWrappersMixin:
    """QML entry points for starting a search, clearing filters, and results."""

    def execute_search(self):
        """Wrapper for QML to start search."""
        self.perform_search()

    def clear_filters(self):
        """Wrapper for QML to clear search filters."""
        # Uncheck all groups
        for i in range(self.groups_list_widget.count()):
            self.groups_list_widget.item(i).setCheckState(Qt.CheckState.Unchecked)
        # Uncheck all subgroups
        for i in range(self.subgroups_list_widget.count()):
            self.subgroups_list_widget.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.filename_edit.clear()

        # Uncheck all format buttons
        for btn in self.format_buttons.values():
            btn.setChecked(False)

        self.selected_formats.clear()  # pyrefly: ignore [missing-attribute]

        # Uncheck all tags
        for i in range(self.tags_list_widget.count()):
            self.tags_list_widget.item(i).setCheckState(Qt.CheckState.Unchecked)

    def display_results(self, results: List[Dict[str, Any]]):
        """
        Extracts paths and delegates loading to AbstractClassTwoGalleries logic.
        """
        paths = [res.get("file_path") for res in results if res.get("file_path")]

        count = len(paths)
        self.results_count_label.setText(f"Found {count} matching image(s)")

        # Call Base Class method to populate the Found Gallery
        self.start_loading_thumbnails(sorted(paths, key=natural_sort_key))

    def clear_search_data(self):
        """Clears local selection data and widgets."""
        for window in self.open_preview_windows[:]:
            window.close()
        self.open_preview_windows.clear()

        # Call base class to clear galleries
        self.clear_galleries(clear_data=True)


__all__ = ["_QmlWrappersMixin"]
