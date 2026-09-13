"""``SimilarityTab`` -- composed controllers over ``AbstractClassTwoGalleries`` (#544)."""

from __future__ import annotations

import contextlib
import os
import tempfile
from typing import Any, Dict, List, Optional

from backend.src.core.similarity import SimilarityConfig, SimilarityReport, TriageRules
from PySide6.QtCore import Property, QPoint, Signal

from gui.src.helpers.core.similarity_scan_worker import SimilarityScanWorker

from ....classes import AbstractClassTwoGalleries
from ....helpers import DeletionWorker
from ._cluster_model import ClusterListModel
from ._config import SimilarityConfigController
from ._deletion import SimilarityDeletionController
from ._diff_consolidate import SimilarityDiffConsolidateController
from ._directory_browse import SimilarityDirectoryBrowseController
from ._legacy_scan import SimilarityLegacyScanController
from ._properties_preview import SimilarityPropertiesPreviewController
from ._qml_properties import SimilarityQmlPropertiesController
from ._qml_settings import SimilarityQmlSettingsController
from ._similarity_scan import SimilarityScanController
from ._triage_selection import SimilarityTriageSelectionController
from ._ui_builder import SimilarityUIBuilder


class SimilarityTab(AbstractClassTwoGalleries):
    """Similarity Finder with split-panel galleries plus the tiered engine.

    Phase 2 (ui-arch-23/#544): mixins collapsed into composed controllers.
    Gallery inheritance stays -- this tab owns two virtual galleries.

    Consolidates the former DeleteTab: it keeps the two galleries (Scan Results
    and Selected for Deletion), directory/extension deletion, property
    comparison and context menus, and layers the similarity clustering,
    triage, diffing and consolidation on top.
    """

    preview_ready = Signal(str)
    scan_status_changed = Signal(str)
    qml_input_path_changed = Signal(str)

    clusters_changed = Signal()
    scan_running_changed = Signal(bool)
    scan_progress = Signal(int, int)
    diff_ready = Signal(str, float)  # rendered mask path, changed_ratio
    consolidation_done = Signal(str)  # human-readable summary
    reference_dir_changed = Signal(str)
    confidence_threshold_changed = Signal(float)
    selection_changed_qml = Signal()

    scanRunning = Property(bool, SimilarityQmlPropertiesController._get_scan_running, notify=scan_running_changed)
    confidenceThreshold = Property(
        float,
        SimilarityQmlPropertiesController._get_conf_threshold,
        SimilarityQmlPropertiesController._set_conf_threshold,
        notify=confidence_threshold_changed,
    )
    selectedFiles = Property(
        "QStringList", SimilarityQmlPropertiesController._get_selected_files, notify=selection_changed_qml
    )

    def __init__(self, dropdown=True):
        super().__init__()

        self._sim_config = SimilarityConfig()
        self._triage_rules = TriageRules()
        self._report: Optional[SimilarityReport] = None
        self._ref_set: set = set()
        self._cluster_model = ClusterListModel(self)
        self._scan_running = False
        self._sim_worker: Optional[SimilarityScanWorker] = None
        self._diff_dir = os.path.join(tempfile.gettempdir(), "image-toolkit-diffs")
        os.makedirs(self._diff_dir, exist_ok=True)

        self.dropdown = dropdown
        self.worker: Optional[DeletionWorker] = None
        self.duplicate_results: Dict[str, List[str]] = {}

        self.ui_builder = SimilarityUIBuilder(self)
        self.qml_properties = SimilarityQmlPropertiesController(self)
        self.legacy_scan = SimilarityLegacyScanController(self)
        self.similarity_scan = SimilarityScanController(self)
        self.qml_settings = SimilarityQmlSettingsController(self)
        self.triage = SimilarityTriageSelectionController(self)
        self.diff_consolidate = SimilarityDiffConsolidateController(self)
        self.deletion = SimilarityDeletionController(self)
        self.properties_preview = SimilarityPropertiesPreviewController(self)
        self.directory_browse = SimilarityDirectoryBrowseController(self)
        self.config_controller = SimilarityConfigController(self)

        self.ui_builder._build_ui()

    def cancel_loading(self):
        worker = getattr(self, "_sim_worker", None)
        if worker and worker.isRunning():
            worker.requestInterruption()
            worker.wait()
        if self.worker and hasattr(self.worker, "isRunning") and self.worker.isRunning():
            with contextlib.suppress(Exception):
                if hasattr(self.worker, "stop"):
                    self.worker.stop()
                elif hasattr(self.worker, "cancel"):
                    self.worker.cancel()
                self.worker.requestInterruption()
                self.worker.wait()
        with contextlib.suppress(Exception):
            super().cancel_loading()
        if hasattr(self, "dual"):
            self.dual.cancel_loading()
        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        self.cancel_loading()
        super().closeEvent(event)

    def collect(self, mode: str = "files") -> Dict[str, Any]:
        return self.config_controller.collect(mode)

    @staticmethod
    def join_list_str(text: str):
        return SimilarityConfigController.join_list_str(text)

    def get_default_config(self) -> dict:
        return self.config_controller.get_default_config()

    def set_config(self, config: dict):
        return self.config_controller.set_config(config)

    def delete_selected_duplicates(self):
        return self.deletion.delete_selected_duplicates()

    def delete_selected_files_qml(self):
        return self.deletion.delete_selected_files_qml()

    def delete_single_file(self, path: str):
        return self.deletion.delete_single_file(path)

    def start_deletion(self, mode: str):
        return self.deletion.start_deletion(mode)

    def set_require_confirm(self, value: bool):
        return self.deletion.set_require_confirm(value)

    def delete_directory_qml(self, target_dir=""):
        return self.deletion.delete_directory_qml(target_dir)

    def list_directory_qml(self, target_dir):
        return self.deletion.list_directory_qml(target_dir)

    def handle_confirmation_request(self, message: str, total_items: int):
        return self.deletion.handle_confirmation_request(message, total_items)

    def update_progress(self, deleted, total):
        return self.deletion.update_progress(deleted, total)

    def on_deletion_done(self, count, msg):
        return self.deletion.on_deletion_done(count, msg)

    def on_deletion_error(self, msg):
        return self.deletion.on_deletion_error(msg)

    def generate_diff(self, path_a: str, path_b: str) -> str:
        return self.diff_consolidate.generate_diff(path_a, path_b)

    def consolidate_selected(self, mode: str = "auto"):
        return self.diff_consolidate.consolidate_selected(mode)

    def browse_directory(self):
        return self.directory_browse.browse_directory()

    def browse_and_populate(self):
        return self.directory_browse.browse_and_populate()

    def browse_reference_directory(self):
        return self.directory_browse.browse_reference_directory()

    def _clear_reference_widget(self):
        return self.directory_browse._clear_reference_widget()

    def browse_target_qml(self, current_path=""):
        return self.directory_browse.browse_target_qml(current_path)

    def is_valid(self, mode: str):
        return self.directory_browse.is_valid(mode)

    def toggle_extension(self, ext, checked):
        return self.directory_browse.toggle_extension(ext, checked)

    def add_all_extensions(self):
        return self.directory_browse.add_all_extensions()

    def remove_all_extensions(self):
        return self.directory_browse.remove_all_extensions()

    def on_scan_button_clicked(self):
        return self.legacy_scan.on_scan_button_clicked()

    def reset_gallery(self):
        return self.legacy_scan.reset_gallery()

    def start_duplicate_scan(self):
        return self.legacy_scan.start_duplicate_scan()

    def _current_extensions(self) -> list:
        return self.legacy_scan._current_extensions()

    def _list_all_files(self, target_dir: str, extensions: list):
        return self.legacy_scan._list_all_files(target_dir, extensions)

    def _prefs(self) -> dict:
        return self.properties_preview._prefs()

    def get_image_properties(self, file_path: str) -> Dict[str, Any]:
        return self.properties_preview.get_image_properties(file_path)

    def show_image_context_menu(self, global_pos: QPoint, path: str):
        return self.properties_preview.show_image_context_menu(global_pos, path)

    def show_image_properties_dialog(self, path: str):
        return self.properties_preview.show_image_properties_dialog(path)

    def show_comparison_dialog(self):
        return self.properties_preview.show_comparison_dialog()

    def open_full_preview(self, image_path: str):
        return self.properties_preview.open_full_preview(image_path)

    def on_selection_changed(self):
        return self.qml_properties.on_selection_changed()

    def set_similarity_settings(self, values: dict):
        return self.qml_settings.set_similarity_settings(values)

    def get_similarity_settings(self):
        return self.qml_settings.get_similarity_settings()

    def set_triage_rules(self, values: dict):
        return self.qml_settings.set_triage_rules(values)

    def get_triage_rules(self):
        return self.qml_settings.get_triage_rules()

    def browse_reference_qml(self, current_path=""):
        return self.qml_settings.browse_reference_qml(current_path)

    def clear_reference_dir(self):
        return self.qml_settings.clear_reference_dir()

    def start_similarity_scan_qml(self, target_dir: str):
        return self.similarity_scan.start_similarity_scan_qml(target_dir)

    def start_duplicate_scan_qml(self, target_dir, method="Exact Match"):
        return self.similarity_scan.start_duplicate_scan_qml(target_dir, method)

    def cancel_similarity_scan(self):
        return self.similarity_scan.cancel_similarity_scan()

    def _set_running(self, running: bool):
        return self.similarity_scan._set_running(running)

    def _on_sim_status(self, message: str):
        return self.similarity_scan._on_sim_status(message)

    def _finalize_scan(self):
        return self.similarity_scan._finalize_scan()

    def _on_sim_scan_finished(self, report: SimilarityReport):
        return self.similarity_scan._on_sim_scan_finished(report)

    def _on_sim_scan_error(self, message: str):
        return self.similarity_scan._on_sim_scan_error(message)

    def _on_sim_scan_cancelled(self):
        return self.similarity_scan._on_sim_scan_cancelled()

    def _apply_clusters(self, clusters: List[dict]):
        return self.similarity_scan._apply_clusters(clusters)

    def set_confidence_threshold(self, value: float):
        return self.similarity_scan.set_confidence_threshold(value)

    def _select_paths(self, paths):
        return self.triage._select_paths(paths)

    def _deselect_paths(self, paths):
        return self.triage._deselect_paths(paths)

    def cluster_paths(self, cluster_id: str):
        return self.triage.cluster_paths(cluster_id)

    def auto_select_cluster(self, cluster_id: str):
        return self.triage.auto_select_cluster(cluster_id)

    def auto_select_all(self):
        return self.triage.auto_select_all()

    def is_selected(self, path: str) -> bool:
        return self.triage.is_selected(path)

    def toggle_selection(self, path: str):
        return self.triage.toggle_selection(path)

    def _sync_selection_from_dual(self):
        return self.triage._sync_selection_from_dual()

    def _push_selection_to_dual(self):
        return self.triage._push_selection_to_dual()

    def refresh_found_gallery(self):
        return self.triage.refresh_found_gallery()

    def refresh_selected_panel(self):
        return self.triage.refresh_selected_panel()

    def clear_galleries(self, clear_data=True):
        return self.triage.clear_galleries(clear_data=clear_data)

    def select_file_qml(self, path):
        return self.triage.select_file_qml(path)


__all__ = ["SimilarityTab", "ClusterListModel"]
