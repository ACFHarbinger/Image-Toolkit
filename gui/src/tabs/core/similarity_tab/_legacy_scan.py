"""Legacy single-method scanning dispatched from the scan-method combo box.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import os

from backend.src.constants import SUPPORTED_IMG_FORMATS
from PySide6.QtWidgets import QMessageBox

from ....utils.sort_utils import natural_sort_key


class _LegacyScanMixin:
    """Combo-box-driven scan dispatch: full similarity engine or a single tier."""

    def on_scan_button_clicked(self):
        """The scan button doubles as a cancel button: cancel a running scan,
        otherwise start a new one."""
        if self._scan_running:
            self.cancel_similarity_scan()
        else:
            self.start_duplicate_scan()

    def reset_gallery(self):
        """Clear any similarity clustering and re-display every image in the
        Source directory (the full listing) in the thumbnail gallery."""
        target_dir = self.target_path.text().strip()
        if not target_dir or not os.path.isdir(target_dir):
            QMessageBox.warning(self, "Invalid Source",
                "Select a valid Source directory to display.")
            return
        self._report = None
        self._ref_set = set()
        self._cluster_model.set_clusters([])
        self.clusters_changed.emit()
        self._deselect_paths(list(self.selected_files))
        self.on_selection_changed()
        self._list_all_files(target_dir, self._current_extensions())

    def start_duplicate_scan(self):
        """Widget-mode scan dispatched from the combo box. The default option
        runs the full tiered similarity engine; the others map to single
        detection tiers for a quick, focused scan."""
        target_dir = self.target_path.text().strip()
        if not target_dir or not os.path.isdir(target_dir):
            QMessageBox.warning(self, "Invalid Source",
                "Please select a valid Source directory to search.")
            return

        # Pick up the optional Target directory to compare the Source against.
        ref_dir = self.reference_path.text().strip()
        self._sim_config.reference_dir = ref_dir if os.path.isdir(ref_dir) else None
        self._sim_config.recursive = self.recursive_check.isChecked()

        extensions = self._current_extensions()
        method_text = self.scan_method_combo.currentText()

        if "Similarity Engine" in method_text:
            self._sim_config.tiers = ["exact", "perceptual"]
        elif "All Files" in method_text:
            self._list_all_files(target_dir, extensions)
            return
        elif "Exact Match" in method_text:
            self._sim_config.tiers = ["exact"]
        elif "Perceptual Hash" in method_text:
            self._sim_config.tiers = ["perceptual"]
        elif "SSIM" in method_text or "ORB" in method_text or "SIFT" in method_text:
            self._sim_config.tiers = ["perceptual", "structural"]
            self._sim_config.feature_method = "sift" if "SIFT" in method_text else "orb"
        else:
            self._sim_config.tiers = ["exact", "perceptual"]

        if extensions:
            self._sim_config.extensions = extensions
        self.start_similarity_scan_qml(target_dir)

    def _current_extensions(self) -> list:
        if self.dropdown and self.selected_extensions:
            return list(self.selected_extensions)
        if not self.dropdown and hasattr(self, "target_extensions"):
            return self.join_list_str(self.target_extensions.text().strip())
        return list(SUPPORTED_IMG_FORMATS)

    def _list_all_files(self, target_dir: str, extensions: list):
        from backend.src.core import SimilarityFinder

        exts = extensions or list(SUPPORTED_IMG_FORMATS)
        recursive = self.recursive_check.isChecked() if hasattr(self, "recursive_check") else False
        images = SimilarityFinder.get_images_list(
            target_dir, exts, recursive=recursive
        )
        self.duplicate_results = {str(i): [p] for i, p in enumerate(images)}
        self._cluster_model.set_clusters([])
        self.clusters_changed.emit()
        if images:
            self.status_label.setText(f"Listed {len(images)} files.")
            self.start_loading_thumbnails(sorted(images, key=natural_sort_key))
        else:
            self.status_label.setText("No supported files found.")


__all__ = ["_LegacyScanMixin"]
