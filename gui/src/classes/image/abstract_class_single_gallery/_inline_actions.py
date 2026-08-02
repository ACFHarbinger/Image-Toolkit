"""Inline rename, export-paths, and copy-to-folder (GUI/UX §2.19 / §2.26B).

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.
"""

from __future__ import annotations

import os
import shutil

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox


class _InlineActionsMixin:
    """Rename-in-place (F2), export selected paths, and copy-to-folder."""

    def _rename_selected_file(self) -> None:
        """Rename the most-recently-selected gallery item via F2 (GUI/UX §2.26B)."""
        target = self.selected_files[-1] if self.selected_files else None
        if target is None and self.gallery_image_paths:
            target = self.gallery_image_paths[0]  # fallback: first visible
        if not target:
            return

        old_name = os.path.basename(target)
        stem, ext = os.path.splitext(old_name)
        new_stem, ok = QInputDialog.getText(
            self, "Rename File", "New name (no extension):", text=stem
        )
        if not ok or not new_stem.strip() or new_stem.strip() == stem:
            return

        new_stem = new_stem.strip()
        for ch in r'\/:*?"<>|':
            new_stem = new_stem.replace(ch, "_")

        new_path = os.path.join(os.path.dirname(target), new_stem + ext)
        if os.path.exists(new_path):
            QMessageBox.warning(
                self, "Rename", f"A file named '{new_stem + ext}' already exists."
            )
            return

        try:
            os.rename(target, new_path)
        except OSError as exc:
            QMessageBox.critical(self, "Rename Error", str(exc))
            return

        for lst in (self.gallery_image_paths, self.master_image_paths, self.selected_files):
            try:
                idx = lst.index(target)
                lst[idx] = new_path
            except (ValueError, AttributeError):
                pass

        widget = getattr(self, "path_to_card_widget", {}).pop(target, None)
        if widget is not None:
            self.path_to_card_widget[new_path] = widget
            if hasattr(widget, "path"):
                widget.path = new_path
            if hasattr(widget, "setToolTip"):
                widget.setToolTip(os.path.basename(new_path))

    def _export_selection_as_paths(self) -> None:
        """Write selected (or all visible) paths to a TXT file (Ctrl+E)."""
        paths = self.selected_files or self.gallery_image_paths
        if not paths:
            QMessageBox.information(self, "Export", "No files to export.")
            return
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export File Paths",
            "",
            "Text files (*.txt);;CSV files (*.csv);;All files (*.*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not dest:
            return
        try:
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write("\n".join(paths))
            QMessageBox.information(
                self, "Export", f"Exported {len(paths)} paths to:\n{dest}"
            )
        except OSError as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    def _copy_selection_to_folder(self) -> None:
        """Copy the current selection (or all visible) to a chosen folder (§2.19C)."""
        paths = list(self.selected_files) if self.selected_files else list(self.gallery_image_paths)
        if not paths:
            QMessageBox.information(self, "Copy to Folder", "No files to copy.")
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
        QMessageBox.information(self, "Copy to Folder", msg)


__all__ = ["_InlineActionsMixin"]
