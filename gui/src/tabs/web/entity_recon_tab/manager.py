"""``EntityReconTab`` -- composed controllers over ``QWidget`` (#544)."""

from __future__ import annotations

import os
import tempfile
from typing import List, Optional

from backend.src.web.recon import ReconConfig, ReconEngine
from backend.src.web.recon.provenance import ProvenanceReport
from PySide6.QtWidgets import QTreeWidgetItem, QWidget

from ._batch_builder import EntityReconBatchController
from ._config import EntityReconConfigController
from ._dataset_indexing import EntityReconDatasetController
from ._identity_resolution import EntityReconIdentityController
from ._library_link import EntityReconLibraryLinkController
from ._lifecycle import EntityReconLifecycleController
from ._provenance_export import EntityReconExportController
from ._source_image import EntityReconSourceController
from ._status_helpers import EntityReconStatusController
from ._ui_builder import EntityReconUIBuilder
from ._worker_plumbing import EntityReconWorkerController


class EntityReconTab(QWidget):
    """Native three-pane Entity Recon and Provenance tab.

    Phase 2 (ui-arch-23/#544): mixins collapsed into composed controllers.
    closeEvent directly overrides QWidget with zero MRO hazard.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = ReconConfig()
        self._engine: Optional[ReconEngine] = None
        self._indexer = None
        self._report: Optional[ProvenanceReport] = None

        self._source_path = ""
        self._source_rgb = None  # np.ndarray (RGB)
        self._cur_alpha = None
        self._cur_bbox = None
        self._batch_rows: List[dict] = []

        self._tmp_dir = os.path.join(tempfile.gettempdir(), "image-toolkit-recon")
        os.makedirs(self._tmp_dir, exist_ok=True)
        self._threads: list = []
        self._warmed_modes: set = set()

        self.ui_builder = EntityReconUIBuilder(self)
        self.status_controller = EntityReconStatusController(self)
        self.config_controller = EntityReconConfigController(self)
        self.dataset_controller = EntityReconDatasetController(self)
        self.source_controller = EntityReconSourceController(self)
        self.identity_controller = EntityReconIdentityController(self)
        self.library_link_controller = EntityReconLibraryLinkController(self)
        self.export_controller = EntityReconExportController(self)
        self.batch_controller = EntityReconBatchController(self)
        self.worker_controller = EntityReconWorkerController(self)
        self.lifecycle_controller = EntityReconLifecycleController(self)

        self.ui_builder._build_ui()

    # ------------------------------------------------------------------
    # Status facade
    # ------------------------------------------------------------------
    def _set_status(self, msg: str):
        return self.status_controller._set_status(msg)

    def _set_busy(self, busy: bool):
        return self.status_controller._set_busy(busy)

    # ------------------------------------------------------------------
    # Config facade
    # ------------------------------------------------------------------
    def _on_embed_changed(self, idx: int):
        return self.config_controller._on_embed_changed(idx)

    def _apply_scope(self, scope: str):
        return self.config_controller._apply_scope(scope)

    def _on_scope_changed(self, idx: int):
        return self.config_controller._on_scope_changed(idx)

    # ------------------------------------------------------------------
    # Dataset indexing facade
    # ------------------------------------------------------------------
    def _browse_dataset(self):
        return self.dataset_controller._browse_dataset()

    def _browse_target(self):
        return self.dataset_controller._browse_target()

    def _build_index(self):
        return self.dataset_controller._build_index()

    def _on_index_built(self, indexer, stats):
        return self.dataset_controller._on_index_built(indexer, stats)

    # ------------------------------------------------------------------
    # Source image facade
    # ------------------------------------------------------------------
    def _browse_source(self):
        return self.source_controller._browse_source()

    def _load_source(self, path: str):
        return self.source_controller._load_source(path)

    def _on_image_clicked(self, x: int, y: int):
        return self.source_controller._on_image_clicked(x, y)

    def _show_overlay(self, alpha):
        return self.source_controller._show_overlay(alpha)

    # ------------------------------------------------------------------
    # Identity resolution facade
    # ------------------------------------------------------------------
    def _resolve(self):
        return self.identity_controller._resolve()

    def _on_resolved(self, res):
        return self.identity_controller._on_resolved(res)

    def _on_prov_activated(self, item: QTreeWidgetItem, col: int):
        return self.identity_controller._on_prov_activated(item, col)

    def _open_in_file_manager(self, path: str):
        return self.identity_controller._open_in_file_manager(path)

    # ------------------------------------------------------------------
    # Library link facade
    # ------------------------------------------------------------------
    def _on_prov_context_menu(self, pos) -> None:
        return self.library_link_controller._on_prov_context_menu(pos)

    def _link_match_to_library(self, path: str) -> None:
        return self.library_link_controller._link_match_to_library(path)

    def _resolve_entity_id(self, entity_repo, name: str) -> Optional[str]:
        return self.library_link_controller._resolve_entity_id(entity_repo, name)

    # ------------------------------------------------------------------
    # Provenance export facade
    # ------------------------------------------------------------------
    def _export(self, fmt: str):
        return self.export_controller._export(fmt)

    # ------------------------------------------------------------------
    # Batch builder facade
    # ------------------------------------------------------------------
    def _browse_batch(self):
        return self.batch_controller._browse_batch()

    def _on_batch(self, suggestions):
        return self.batch_controller._on_batch(suggestions)

    def _approve_batch(self):
        return self.batch_controller._approve_batch()

    # ------------------------------------------------------------------
    # Worker plumbing facade
    # ------------------------------------------------------------------
    def _warm_embedder(self) -> None:
        return self.worker_controller._warm_embedder()

    def _run_worker(self, worker, on_finished):
        return self.worker_controller._run_worker(worker, on_finished)

    def _reap_worker(self, worker):
        return self.worker_controller._reap_worker(worker)

    def _on_worker_error(self, message: str):
        return self.worker_controller._on_worker_error(message)

    # ------------------------------------------------------------------
    # Lifecycle & QWidget overrides
    # ------------------------------------------------------------------
    def cancel_loading(self):
        return self.lifecycle_controller.cancel_loading()

    def closeEvent(self, event):
        self.cancel_loading()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # UI builder facade
    # ------------------------------------------------------------------
    def _build_ui(self):
        return self.ui_builder._build_ui()


__all__ = ["EntityReconTab"]
