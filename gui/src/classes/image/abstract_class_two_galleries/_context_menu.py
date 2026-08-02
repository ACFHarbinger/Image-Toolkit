"""Shift+click range-select and the found-gallery right-click context menu.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change (see ``_navigation.py``'s docstring).
"""

from __future__ import annotations

import contextlib
import os
import shutil

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox
from send2trash import send2trash  # pyrefly: ignore [untyped-import]


class _ContextMenuMixin:
    """§2.4B shift-range-select and §2.4C found-gallery right-click menu."""

    # §2.4B — Shift+click range select ----------------------------------
    @Slot(str)
    def _on_found_card_clicked(self, path: str) -> None:
        """Handle left-click on a found-gallery card, supporting Shift+range."""
        modifiers = QApplication.keyboardModifiers()
        page_paths = self.common_get_paginated_slice(
            self.master_found_files, self.found_current_page, self.found_page_size
        )
        try:
            clicked_idx = page_paths.index(path)
        except ValueError:
            self.toggle_selection(path)
            return

        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            anchor = getattr(self, "_selection_anchor_idx", clicked_idx)
            lo, hi = sorted([anchor, clicked_idx])
            for p in page_paths[lo : hi + 1]:
                if p not in self.selected_files:
                    self.selected_files.append(p)
            self._update_found_card_styles()
            self.refresh_selected_panel()
            self.on_selection_changed()
        else:
            self._selection_anchor_idx = clicked_idx
            self.toggle_selection(path)

    # §2.4C — right-click context menu on found-gallery cards -----------
    @Slot(object, str)
    def _on_found_card_right_clicked(self, global_pos, path: str) -> None:
        menu = QMenu(self)

        open_act = QAction("Open Preview", menu)
        open_act.triggered.connect(lambda: self._open_preview_for(path))
        menu.addAction(open_act)

        menu.addSeparator()

        sel_lbl = "Deselect" if path in self.selected_files else "Select"
        sel_act = QAction(sel_lbl, menu)
        sel_act.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(sel_act)

        sel_all_act = QAction("Select All", menu)
        sel_all_act.triggered.connect(self.select_all_items)
        menu.addAction(sel_all_act)

        desel_act = QAction("Deselect All", menu)
        desel_act.triggered.connect(self.deselect_all_items)
        menu.addAction(desel_act)

        menu.addSeparator()

        rename_act = QAction("Rename…  (F2)", menu)
        rename_act.triggered.connect(self._rename_focused_file)
        menu.addAction(rename_act)

        trash_act = QAction("Move to Trash", menu)
        trash_act.triggered.connect(lambda: self._trash_path(path))
        menu.addAction(trash_act)

        menu.addSeparator()

        export_act = QAction("Export Paths…  (Ctrl+E)", menu)
        export_act.triggered.connect(self._export_selection_as_paths)
        menu.addAction(export_act)

        copy_act = QAction("Copy Selection to Folder…", menu)
        copy_act.triggered.connect(self._copy_selection_to_folder)
        menu.addAction(copy_act)

        menu.addSeparator()

        # Color label submenu (§2.18B)
        label_menu = menu.addMenu("Color Label")
        current_label = self._get_color_label(path)
        for key, _hex_color in self._LABEL_COLORS.items():
            icon_txt = self._LABEL_ICONS.get(key, "")
            lbl_act = QAction(f"{icon_txt} {key.capitalize()}", label_menu)
            lbl_act.setCheckable(True)
            lbl_act.setChecked(current_label == key)
            lbl_act.triggered.connect(
                lambda checked=False, k=key: self._set_color_label(
                    path, None if self._get_color_label(path) == k else k
                )
            )
            label_menu.addAction(lbl_act)
        label_menu.addSeparator()
        clear_act = QAction("Clear Label", label_menu)
        clear_act.setEnabled(current_label is not None)
        clear_act.triggered.connect(lambda: self._set_color_label(path, None))
        label_menu.addAction(clear_act)

        menu.exec(global_pos)

    def _open_preview_for(self, path: str) -> None:
        widget = self.path_to_label_map.get(path)
        if widget and hasattr(widget, "path_double_clicked"):
            widget.path_double_clicked.emit(path)

    def _confirm_deletions_enabled(self) -> bool:
        """Return True if the user's preference requires a confirmation dialog before deletion (§2.9D)."""
        try:
            main_win = self.window()
            if main_win and hasattr(main_win, "cached_creds"):
                return bool(main_win.cached_creds.get("preferences", {}).get("confirm_deletions", True))
        except Exception:
            pass
        return True

    def _trash_path(self, path: str) -> None:
        if self._confirm_deletions_enabled():
            answer = QMessageBox.question(
                self,
                "Move to Trash",
                f'Move "{os.path.basename(path)}" to trash?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            send2trash(path)
        except Exception as exc:
            QMessageBox.critical(self, "Move to Trash", str(exc))
            return
        for lst in (self.found_files, self.master_found_files, self.selected_files):
            with contextlib.suppress(ValueError):
                lst.remove(path)
        self.path_to_label_map.pop(path, None)
        self._update_found_card_styles()
        self.refresh_selected_panel()
        self.on_selection_changed()
        self._show_status(f"Moved to trash: {os.path.basename(path)}")

    def _copy_selection_to_folder(self) -> None:
        """Copy the current selection (or found list if no selection) to a chosen folder (§2.19C)."""
        paths = list(self.selected_files) if self.selected_files else list(self.found_files)
        if not paths:
            self._show_status("Nothing to copy — gallery is empty.")
            return
        dest_dir = QFileDialog.getExistingDirectory(
            self,
            "Copy Selection to Folder",
            "",
            QFileDialog.Option.DontUseNativeDialog,
        )
        if not dest_dir:
            return
        copied, skipped = 0, 0
        for src in paths:
            dst = os.path.join(dest_dir, os.path.basename(src))
            if os.path.exists(dst):
                skipped += 1
                continue
            try:
                shutil.copy2(src, dst)
                copied += 1
            except OSError as exc:
                QMessageBox.critical(self, "Copy Error", f"Failed to copy {os.path.basename(src)}:\n{exc}")
                return
        msg = f"Copied {copied} file(s) to {os.path.basename(dest_dir)}"
        if skipped:
            msg += f" ({skipped} skipped — already exist)"
        self._show_status(msg)


__all__ = ["_ContextMenuMixin"]
