"""``EntityReconTab`` -- composed from per-concern mixins."""

from __future__ import annotations

import os
import tempfile
from typing import List, Optional

from backend.src.web.recon import ReconConfig, ReconEngine
from backend.src.web.recon.provenance import ProvenanceReport
from PySide6.QtWidgets import QWidget

from ._batch_builder import _BatchBuilderMixin
from ._config import _ConfigMixin
from ._dataset_indexing import _DatasetIndexingMixin
from ._identity_resolution import _IdentityResolutionMixin
from ._lifecycle import _LifecycleMixin
from ._provenance_export import _ProvenanceExportMixin
from ._source_image import _SourceImageMixin
from ._status_helpers import _StatusHelpersMixin
from ._ui_builder import _UIBuilderMixin
from ._worker_plumbing import _WorkerPlumbingMixin


class EntityReconTab(
    # Mixins MUST precede QWidget in MRO order (see gui/src/tabs/core/
    # merge_tab/manager.py for the bug this pattern fixes): _LifecycleMixin's
    # closeEvent overrides a method QWidget itself defines.
    _UIBuilderMixin,
    _StatusHelpersMixin,
    _ConfigMixin,
    _DatasetIndexingMixin,
    _SourceImageMixin,
    _IdentityResolutionMixin,
    _ProvenanceExportMixin,
    _BatchBuilderMixin,
    _WorkerPlumbingMixin,
    _LifecycleMixin,
    QWidget,
):
    """Native three-pane Entity Recon and Provenance tab."""

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

        self._build_ui()


__all__ = ["EntityReconTab"]
