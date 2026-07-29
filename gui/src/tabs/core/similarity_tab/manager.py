"""``SimilarityTab`` -- composed from per-concern mixins."""

from __future__ import annotations

import os
import tempfile
from typing import Dict, List, Optional

from backend.src.core.similarity import SimilarityConfig, SimilarityReport, TriageRules
from gui.src.helpers.core.similarity_scan_worker import SimilarityScanWorker
from PySide6.QtCore import Property, Signal

from ....classes import AbstractClassTwoGalleries
from ....helpers import DeletionWorker
from ._cluster_model import ClusterListModel
from ._config import _ConfigMixin
from ._deletion import _DeletionMixin
from ._diff_consolidate import _DiffConsolidateMixin
from ._directory_browse import _DirectoryBrowseMixin
from ._legacy_scan import _LegacyScanMixin
from ._lifecycle import _LifecycleMixin
from ._properties_preview import _PropertiesPreviewMixin
from ._qml_properties import _QmlPropertiesMixin
from ._qml_settings import _QmlSettingsMixin
from ._similarity_scan import _SimilarityScanMixin
from ._triage_selection import _TriageSelectionMixin
from ._ui_builder import _UIBuilderMixin


class SimilarityTab(
    # Mixins MUST precede AbstractClassTwoGalleries in MRO order (see
    # gui/src/tabs/core/merge_tab/manager.py for the bug this pattern
    # fixes): several mixin methods here (cancel_loading, closeEvent,
    # create_card_widget, get_default_config, on_selection_changed,
    # set_config, toggle_selection, update_card_pixmap) override same-named
    # methods AbstractClassTwoGalleries itself defines.
    _UIBuilderMixin,
    _QmlPropertiesMixin,
    _LegacyScanMixin,
    _SimilarityScanMixin,
    _QmlSettingsMixin,
    _TriageSelectionMixin,
    _DiffConsolidateMixin,
    _DeletionMixin,
    _PropertiesPreviewMixin,
    _DirectoryBrowseMixin,
    _ConfigMixin,
    _LifecycleMixin,
    AbstractClassTwoGalleries,
):
    """Similarity Finder with split-panel galleries plus the tiered engine.

    Consolidates the former DeleteTab: it keeps the two galleries (Scan Results
    and Selected for Deletion), directory/extension deletion, property
    comparison and context menus, and layers the similarity clustering,
    triage, diffing and consolidation on top.
    """

    preview_ready = Signal(str)
    scan_status_changed = Signal(str)
    qml_input_path_changed = Signal(str)

    # similarity signals
    clusters_changed = Signal()
    scan_running_changed = Signal(bool)
    scan_progress = Signal(int, int)
    diff_ready = Signal(str, float)          # rendered mask path, changed_ratio
    consolidation_done = Signal(str)         # human-readable summary
    reference_dir_changed = Signal(str)
    confidence_threshold_changed = Signal(float)
    selection_changed_qml = Signal()

    scanRunning = Property(
        bool, _QmlPropertiesMixin._get_scan_running, notify=scan_running_changed
    )
    confidenceThreshold = Property(
        float,
        _QmlPropertiesMixin._get_conf_threshold,
        _QmlPropertiesMixin._set_conf_threshold,
        notify=confidence_threshold_changed,
    )
    selectedFiles = Property(
        "QStringList", _QmlPropertiesMixin._get_selected_files, notify=selection_changed_qml
    )

    def __init__(self, dropdown=True):
        super().__init__()

        # --- similarity state (set before UI, clear_galleries touches threads)
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

        self._build_ui()


__all__ = ["SimilarityTab", "ClusterListModel"]
