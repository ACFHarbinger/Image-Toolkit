"""Similarity Finder tab — the consolidated replacement for the Delete tab.

This single tab now owns the full duplicate/deletion workflow that used to
live in ``DeleteTab`` (directory listing, extension filtering, standard file
and directory deletion, property comparison, context menus) *and* the tiered
similarity engine on top of it (exact/perceptual/structural/semantic
clustering, smart triage, visual diffing, hardlink consolidation).

QML API surface (``mainBackend.similarityTab``, alias ``deleteTab``):
    Properties : clusterModel, scanRunning, confidenceThreshold, selectedFiles
    Slots      : start_similarity_scan_qml, cancel_similarity_scan,
                 set_similarity_settings / get_similarity_settings,
                 set_triage_rules / get_triage_rules, set_confidence_threshold,
                 auto_select_all, auto_select_cluster, generate_diff,
                 consolidate_selected, cluster_paths, browse_target_qml,
                 start_duplicate_scan_qml, delete_selected_files_qml,
                 delete_directory_qml, list_directory_qml, select_file_qml
    Signals    : clusters_changed, scan_running_changed, scan_progress,
                 scan_status_changed, diff_ready, consolidation_done,
                 qml_input_path_changed
"""

import contextlib
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.src.constants import SUPPORTED_IMG_FORMATS
from backend.src.core.similarity import (
    SimilarityConfig,
    SimilarityEngine,
    SimilarityReport,
    TriageRules,
    auto_select,
    consolidate_cluster,
)
from PIL import Image
from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QPoint,
    Qt,
    QThread,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from ...classes import AbstractClassTwoGalleries
from ...components import (
    ClickableLabel,
    MarqueeScrollArea,
    OptionalField,
    PropertyComparisonDialog,
)
from ...helpers import DeletionWorker
from ...helpers.core.similarity_scan_worker import SimilarityScanWorker
from ...styles import apply_shadow_effect
from ...utils.sort_utils import natural_sort_key
from ...windows import ImagePreviewWindow

logger = logging.getLogger(__name__)


class ClusterListModel(QAbstractListModel):
    """Cluster ("stack"/"album") list for the QML gallery."""

    ClusterIdRole = Qt.ItemDataRole.UserRole + 1
    PathsRole = Qt.ItemDataRole.UserRole + 2
    SizeRole = Qt.ItemDataRole.UserRole + 3
    ConfidenceRole = Qt.ItemDataRole.UserRole + 4
    TierRole = Qt.ItemDataRole.UserRole + 5
    KeeperRole = Qt.ItemDataRole.UserRole + 6
    ReferencePathsRole = Qt.ItemDataRole.UserRole + 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clusters: List[dict] = []

    def roleNames(self):
        return {
            self.ClusterIdRole: QByteArray(b"clusterId"),
            self.PathsRole: QByteArray(b"paths"),
            self.SizeRole: QByteArray(b"clusterSize"),
            self.ConfidenceRole: QByteArray(b"confidence"),
            self.TierRole: QByteArray(b"tier"),
            self.KeeperRole: QByteArray(b"keeperPath"),
            self.ReferencePathsRole: QByteArray(b"referencePaths"),
        }

    def rowCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0
        return len(self._clusters)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._clusters)):
            return None
        c = self._clusters[index.row()]
        if role == self.ClusterIdRole:
            return c["id"]
        if role == self.PathsRole:
            return c["paths"]
        if role == self.SizeRole:
            return c["size"]
        if role == self.ConfidenceRole:
            return c["confidence"]
        if role == self.TierRole:
            return c["tier"]
        if role == self.KeeperRole:
            return c.get("keeper", "")
        if role == self.ReferencePathsRole:
            return c.get("reference_paths", [])
        return None

    def set_clusters(self, clusters: List[dict]):
        self.beginResetModel()
        self._clusters = clusters
        self.endResetModel()

    def set_keeper(self, cluster_id: str, keeper: str):
        for row, c in enumerate(self._clusters):
            if c["id"] == cluster_id:
                c["keeper"] = keeper
                idx = self.index(row)
                self.dataChanged.emit(idx, idx, [self.KeeperRole])
                return

    def clusters(self) -> List[dict]:
        return self._clusters

    def get(self, cluster_id: str) -> Optional[dict]:
        for c in self._clusters:
            if c["id"] == cluster_id:
                return c
        return None


class SimilarityTab(AbstractClassTwoGalleries):
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

    def __init__(self, dropdown=True):
        super().__init__()

        # --- similarity state (set before UI, clear_galleries touches threads)
        self._sim_config = SimilarityConfig()
        self._triage_rules = TriageRules()
        self._report: Optional[SimilarityReport] = None
        self._ref_set: set = set()
        self._cluster_model = ClusterListModel(self)
        self._scan_running = False
        self._sim_thread: Optional[QThread] = None
        self._sim_worker: Optional[SimilarityScanWorker] = None
        self._diff_dir = os.path.join(tempfile.gettempdir(), "image-toolkit-diffs")
        os.makedirs(self._diff_dir, exist_ok=True)

        self.dropdown = dropdown
        self.worker: Optional[DeletionWorker] = None
        self.duplicate_results: Dict[str, List[str]] = {}

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # --- 1. Target Group ---
        target_group = QGroupBox("Similarity Target")
        target_layout = QFormLayout(target_group)
        v_target_group = QVBoxLayout()

        browse_layout = QHBoxLayout()
        self.target_path = QLineEdit()
        self.target_path.setPlaceholderText("Path to scan for duplicates / delete...")
        self.target_path.returnPressed.connect(self.start_duplicate_scan)
        browse_layout.addWidget(self.target_path)

        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_directory)
        apply_shadow_effect(btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        browse_layout.addWidget(btn_browse_scan)

        v_target_group.addLayout(browse_layout)
        target_layout.addRow("Target path:", v_target_group)
        content_layout.addWidget(target_group)

        # --- 2. Options Group ---
        settings_group = QGroupBox("Scan Settings")
        settings_layout = QFormLayout(settings_group)

        self.scan_method_combo = QComboBox()
        self.scan_method_combo.addItems(
            [
                "Similarity Engine (tiered clusters)",
                "All Files (List Directory Contents)",
                "Exact Match (Same File - Fastest)",
                "Similar: Perceptual Hash (Resized/Color Edits - Fast)",
                "Similar: ORB Feature Matching (Cropped/Rotated - Medium)",
                "Similar: SIFT Feature Matching (Robust - Slow)",
                "Similar: SSIM (High Quality - Slowest)",
            ]
        )
        settings_layout.addRow("Scan Method:", self.scan_method_combo)
        content_layout.addWidget(settings_group)

        # --- 3. Galleries ---
        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setRange(0, 0)
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.hide()
        content_layout.addWidget(self.scan_progress_bar)

        # A. Top Gallery: Found duplicates / cluster members
        self.found_gallery_scroll = MarqueeScrollArea()
        self.found_gallery_scroll.setWidgetResizable(True)
        self.found_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.found_gallery_scroll.setMinimumHeight(600)
        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet("background-color: #2c2f33;")
        self.found_gallery_layout = QGridLayout(self.gallery_widget)
        self.found_gallery_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.found_gallery_scroll.setWidget(self.gallery_widget)
        self.found_gallery_scroll.selection_changed.connect(self.handle_marquee_selection)
        content_layout.addWidget(self.found_search_input)
        content_layout.addWidget(self.found_gallery_scroll, 1)
        if hasattr(self, "found_pagination_widget"):
            content_layout.addWidget(
                self.found_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )

        # B. Bottom Gallery: Selected for Deletion
        self.selected_gallery_scroll = MarqueeScrollArea()
        self.selected_gallery_scroll.setWidgetResizable(True)
        self.selected_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.selected_gallery_scroll.setMinimumHeight(400)
        self.selected_widget = QWidget()
        self.selected_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_gallery_layout = QGridLayout(self.selected_widget)
        self.selected_gallery_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.selected_gallery_scroll.setWidget(self.selected_widget)
        content_layout.addWidget(self.selected_gallery_scroll, 1)
        if hasattr(self, "selected_pagination_widget"):
            content_layout.addWidget(
                self.selected_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )

        # Actions for duplicates
        dup_actions_layout = QHBoxLayout()
        self.btn_compare_properties = QPushButton("Compare Properties (0)")
        apply_shadow_effect(self.btn_compare_properties, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_compare_properties.clicked.connect(self.show_comparison_dialog)
        self.btn_compare_properties.setVisible(False)
        dup_actions_layout.addWidget(self.btn_compare_properties)
        self.btn_delete_selected_dups = QPushButton("Delete Selected Duplicates")
        self.btn_delete_selected_dups.setVisible(False)
        content_layout.addLayout(dup_actions_layout)

        # Extension filter
        self.selected_extensions: Optional[set[str]] = None
        if self.dropdown:
            self.selected_extensions = set()
            ext_layout = QVBoxLayout()
            btn_layout = QHBoxLayout()
            self.extension_buttons = {}
            for ext in SUPPORTED_IMG_FORMATS:
                btn = QPushButton(ext)
                btn.setCheckable(True)
                btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
                apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
                btn.clicked.connect(lambda checked, e=ext: self.toggle_extension(e, checked))
                btn_layout.addWidget(btn)
                self.extension_buttons[ext] = btn
            ext_layout.addLayout(btn_layout)
            all_btn_layout = QHBoxLayout()
            btn_add_all = QPushButton("Add All")
            btn_add_all.setStyleSheet("background-color: green; color: white;")
            apply_shadow_effect(btn_add_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            btn_add_all.clicked.connect(self.add_all_extensions)
            btn_remove_all = QPushButton("Remove All")
            btn_remove_all.setStyleSheet("background-color: red; color: white;")
            apply_shadow_effect(btn_remove_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
            btn_remove_all.clicked.connect(self.remove_all_extensions)
            all_btn_layout.addWidget(btn_add_all)
            all_btn_layout.addWidget(btn_remove_all)
            ext_layout.addLayout(all_btn_layout)
            ext_container = QWidget()
            ext_container.setLayout(ext_layout)
            self.extensions_field = OptionalField("Target extensions", ext_container, start_open=False)
            settings_layout.addRow(self.extensions_field)
        else:
            self.target_extensions = QLineEdit()
            self.target_extensions.setPlaceholderText("e.g. .txt .jpg or txt jpg")
            settings_layout.addRow("Target extensions (optional):", self.target_extensions)

        self.confirm_checkbox = QCheckBox("Require confirmation before delete (recommended)")
        self.confirm_checkbox.setChecked(True)
        settings_layout.addRow(self.confirm_checkbox)

        # --- 4. Standard Delete Buttons ---
        content_layout.addStretch(1)
        run_buttons_layout = QHBoxLayout()
        SHARED_BUTTON_STYLE = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #667eea, stop:1 #764ba2);
                color: white; font-weight: bold; font-size: 14px;
                padding: 14px 8px; border-radius: 10px; min-height: 44px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #764ba2, stop:1 #667eea); }
            QPushButton:disabled { background: #718096; }
            QPushButton:pressed { background: #5a67d8; }
        """
        self.btn_delete_files = QPushButton("Delete Selected Files (0)")
        self.btn_delete_files.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_delete_files, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_delete_files.clicked.connect(self.delete_selected_duplicates)
        self.btn_delete_files.setEnabled(False)

        self.btn_delete_directory = QPushButton("Delete Directory and Contents")
        self.btn_delete_directory.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.btn_delete_directory, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        self.btn_delete_directory.clicked.connect(lambda: self.start_deletion(mode="directory"))

        run_buttons_layout.addWidget(self.btn_delete_directory)
        run_buttons_layout.addWidget(self.btn_delete_files)
        content_layout.addLayout(run_buttons_layout)

        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.status_label)

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll)
        self.setLayout(main_layout)
        self.clear_galleries()

    # ==================================================================
    # QML properties (similarity)
    # ==================================================================

    @Property(QAbstractListModel, constant=True)
    def clusterModel(self):
        return self._cluster_model

    def _get_scan_running(self) -> bool:
        return self._scan_running

    scanRunning = Property(bool, _get_scan_running, notify=scan_running_changed)

    def _get_conf_threshold(self) -> float:
        return self._sim_config.confidence_threshold

    def _set_conf_threshold(self, value: float):
        self.set_confidence_threshold(value)

    confidenceThreshold = Property(
        float, _get_conf_threshold, _set_conf_threshold,
        notify=confidence_threshold_changed,
    )

    def _get_selected_files(self) -> List[str]:
        return sorted(self.selected_files)

    selectedFiles = Property("QStringList", _get_selected_files, notify=selection_changed_qml)

    # ==================================================================
    # Gallery card rendering (from DeleteTab)
    # ==================================================================

    def create_card_widget(self, path: str, pixmap: Optional[QPixmap], is_selected: bool) -> QWidget:
        thumb_size = self.thumbnail_size
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)
        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)
        card_wrapper.set_image_label(img_label)
        if pixmap and not pixmap.isNull():
            img_label.setPixmap(pixmap.scaled(thumb_size, thumb_size,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation))
        else:
            img_label.setText("Loading...")
            img_label.setStyleSheet("color: #999; border: 1px dashed #666;")
        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)
        card_wrapper.path_double_clicked.connect(self.open_full_preview)
        card_wrapper.path_right_clicked.connect(self.show_image_context_menu)
        card_wrapper.set_selected_style(is_selected, self._update_card_style, img_label)
        return card_wrapper

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        try:
            if not isinstance(widget, ClickableLabel):
                return
            img_label = widget.findChild(QLabel)
            if not img_label:
                return
            if pixmap and not pixmap.isNull():
                thumb_size = self.thumbnail_size
                scaled = pixmap.scaled(thumb_size, thumb_size,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                img_label.setPixmap(scaled)
                img_label.setText("")
            else:
                img_label.clear()
                img_label.setText("Loading...")
            is_selected = widget.path in self.selected_files
            self._update_card_style(img_label, is_selected)
        except RuntimeError:
            pass

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        if is_selected:
            img_label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            try:
                px = img_label.pixmap()
                if px and not px.isNull():
                    img_label.setStyleSheet("border: 1px solid #4f545c; background-color: #36393f;")
                else:
                    img_label.setStyleSheet("border: 1px dashed #666; color: #999;")
            except RuntimeError:
                pass

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.btn_delete_files.setText(f"Delete Selected Files ({count})")
        self.btn_delete_files.setEnabled(count > 0)
        self.btn_compare_properties.setText(f"Compare Properties ({count})")
        has_dups = len(self.found_files) > 0
        self.btn_compare_properties.setVisible(has_dups)
        self.btn_compare_properties.setEnabled(count > 0)
        self.selection_changed_qml.emit()

    # ==================================================================
    # Legacy single-method scanning (widget combo box)
    # ==================================================================

    def start_duplicate_scan(self):
        """Widget-mode scan dispatched from the combo box. The default option
        runs the full tiered similarity engine; the others map to single
        detection tiers for a quick, focused scan."""
        target_dir = self.target_path.text().strip()
        if not target_dir or not os.path.isdir(target_dir):
            QMessageBox.warning(self, "Invalid Path",
                "Please select a valid directory in the 'Target path' field to scan.")
            return

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
        from gui.src.windows.settings.app_settings import AppSettings

        exts = extensions or list(SUPPORTED_IMG_FORMATS)
        images = SimilarityFinder.get_images_list(
            target_dir, exts, recursive=AppSettings.recursive_scan()
        )
        self.duplicate_results = {str(i): [p] for i, p in enumerate(images)}
        self._cluster_model.set_clusters([])
        self.clusters_changed.emit()
        if images:
            self.status_label.setText(f"Listed {len(images)} files.")
            self.start_loading_thumbnails(sorted(images, key=natural_sort_key))
        else:
            self.status_label.setText("No supported files found.")

    # ==================================================================
    # Similarity engine scanning
    # ==================================================================

    @Slot(str)
    def start_similarity_scan_qml(self, target_dir: str):
        if self._scan_running:
            return
        if not target_dir or not os.path.isdir(target_dir):
            self.scan_status_changed.emit("Invalid target directory.")
            return
        self._sim_config.target_dir = target_dir
        if self.dropdown and self.selected_extensions:
            self._sim_config.extensions = list(self.selected_extensions)
        self.target_path.setText(target_dir)
        self._set_running(True)
        self.scan_progress_bar.show()
        self.status_label.setText("Starting similarity scan...")
        self.scan_status_changed.emit("Starting similarity scan...")

        self._sim_thread = QThread()
        self._sim_worker = SimilarityScanWorker(self._sim_config)
        self._sim_worker.moveToThread(self._sim_thread)
        self._sim_thread.started.connect(self._sim_worker.run)
        self._sim_worker.status.connect(self._on_sim_status)
        self._sim_worker.progress.connect(self.scan_progress)
        self._sim_worker.finished.connect(self._on_sim_scan_finished)
        self._sim_worker.error.connect(self._on_sim_scan_error)
        self._sim_worker.cancelled.connect(self._on_sim_scan_cancelled)
        for terminal in (self._sim_worker.finished, self._sim_worker.error,
                         self._sim_worker.cancelled):
            terminal.connect(self._sim_thread.quit)
        self._sim_thread.finished.connect(self._sim_worker.deleteLater)
        self._sim_thread.finished.connect(self._on_sim_thread_finished)
        self._sim_thread.finished.connect(self._sim_thread.deleteLater)
        self._sim_thread.start()

    @Slot(str, str)
    def start_duplicate_scan_qml(self, target_dir, method="Exact Match"):
        """Back-compat wrapper: map the old method string to tiers and scan."""
        if not target_dir or not os.path.isdir(target_dir):
            return
        idx = self.scan_method_combo.findText(method, Qt.MatchFlag.MatchContains)
        if idx >= 0:
            self.scan_method_combo.setCurrentIndex(idx)
        self.target_path.setText(target_dir)
        self.start_duplicate_scan()

    @Slot()
    def cancel_similarity_scan(self):
        if self._sim_thread and self._sim_thread.isRunning():
            self._sim_thread.requestInterruption()
            self.scan_status_changed.emit("Cancelling scan...")

    def _set_running(self, running: bool):
        if self._scan_running != running:
            self._scan_running = running
            self.scan_running_changed.emit(running)
        if not running:
            self.scan_progress_bar.hide()

    @Slot(str)
    def _on_sim_status(self, message: str):
        self.status_label.setText(message)
        self.scan_status_changed.emit(message)

    @Slot()
    def _on_sim_thread_finished(self):
        self._sim_thread = None
        self._sim_worker = None
        self._set_running(False)

    @Slot(object)
    def _on_sim_scan_finished(self, report: SimilarityReport):
        self._report = report
        self._ref_set = set()
        if self._sim_config.reference_dir:
            ref = os.path.abspath(self._sim_config.reference_dir)
            self._ref_set = {
                p for p in report.files
                if os.path.commonpath([ref, os.path.abspath(p)]) == ref
            }
        self._apply_clusters(report.clusters)
        n_files = sum(c["size"] for c in report.clusters)
        msg = (f"Scan complete: {len(report.clusters)} clusters, {n_files} files "
               f"({report.stats.get('cache_hits', 0)} cache hits).")
        self.status_label.setText(msg)
        self.scan_status_changed.emit(msg)
        self.duplicate_results = {c["id"]: c["paths"] for c in report.clusters}
        flattened = [p for c in report.clusters for p in c["paths"]]
        if flattened:
            self.start_loading_thumbnails(sorted(flattened, key=natural_sort_key))

    @Slot(str)
    def _on_sim_scan_error(self, message: str):
        self.status_label.setText(f"Scan failed: {message}")
        self.scan_status_changed.emit(f"Scan failed: {message}")

    @Slot()
    def _on_sim_scan_cancelled(self):
        self.status_label.setText("Scan cancelled.")
        self.scan_status_changed.emit("Scan cancelled.")

    def _apply_clusters(self, clusters: List[dict]):
        protected = self._ref_set
        for c in clusters:
            keeper, _ = auto_select(c["paths"], self._triage_rules, protected)
            c["keeper"] = keeper or ""
        self._cluster_model.set_clusters(clusters)
        self.clusters_changed.emit()

    @Slot(float)
    def set_confidence_threshold(self, value: float):
        value = max(0.0, min(1.0, float(value)))
        if abs(value - self._sim_config.confidence_threshold) < 1e-9:
            return
        self._sim_config.confidence_threshold = value
        self.confidence_threshold_changed.emit(value)
        if self._report is not None:
            clusters = SimilarityEngine.regroup(self._report, value, self._ref_set)
            self._apply_clusters(clusters)

    # ==================================================================
    # Settings (QML)
    # ==================================================================

    @Slot("QVariantMap")
    def set_similarity_settings(self, values: dict):
        data = self._sim_config.to_dict()
        for key, val in dict(values).items():
            if key not in data:
                continue
            # An empty extensions list means "use defaults" — never clobber.
            if key == "extensions" and not val:
                continue
            data[key] = val
        self._sim_config = SimilarityConfig.from_dict(data)

    @Slot(result="QVariantMap")
    def get_similarity_settings(self):
        return self._sim_config.to_dict()

    @Slot("QVariantMap")
    def set_triage_rules(self, values: dict):
        data = self._triage_rules.to_dict()
        for key, val in dict(values).items():
            if key in data:
                data[key] = val
        self._triage_rules = TriageRules.from_dict(data)

    @Slot(result="QVariantMap")
    def get_triage_rules(self):
        return self._triage_rules.to_dict()

    @Slot(str, result=str)
    def browse_reference_qml(self, current_path=""):
        starting = current_path if os.path.isdir(current_path) else ""
        d = QFileDialog.getExistingDirectory(self, "Select Reference Directory", starting)
        if d:
            self._sim_config.reference_dir = d
            self.reference_dir_changed.emit(d)
            return d
        return ""

    @Slot()
    def clear_reference_dir(self):
        self._sim_config.reference_dir = None
        self.reference_dir_changed.emit("")

    # ==================================================================
    # Triage / selection
    # ==================================================================

    def _select_paths(self, paths):
        current = set(self.selected_files)
        for p in paths:
            if p not in current:
                self.selected_files.append(p)
                current.add(p)

    def _deselect_paths(self, paths):
        doomed = set(paths)
        self.selected_files[:] = [p for p in self.selected_files if p not in doomed]

    @Slot(str, result="QStringList")
    def cluster_paths(self, cluster_id: str):
        c = self._cluster_model.get(cluster_id)
        return c["paths"] if c else []

    @Slot(str)
    def auto_select_cluster(self, cluster_id: str):
        c = self._cluster_model.get(cluster_id)
        if not c:
            return
        keeper, discards = auto_select(c["paths"], self._triage_rules, self._ref_set)
        if keeper:
            self._cluster_model.set_keeper(cluster_id, keeper)
        self._deselect_paths(c["paths"])
        self._select_paths(discards)
        self.on_selection_changed()

    @Slot()
    def auto_select_all(self):
        for c in self._cluster_model.clusters():
            keeper, discards = auto_select(c["paths"], self._triage_rules, self._ref_set)
            c["keeper"] = keeper or ""
            self._deselect_paths(c["paths"])
            self._select_paths(discards)
        self._cluster_model.set_clusters(self._cluster_model.clusters())
        self.on_selection_changed()

    @Slot(str, result=bool)
    def is_selected(self, path: str) -> bool:
        return path in self.selected_files

    def toggle_selection(self, path: str):
        super().toggle_selection(path)
        self.selection_changed_qml.emit()

    @Slot(str)
    def select_file_qml(self, path):
        self.toggle_selection(path)

    # ==================================================================
    # Visual diffing
    # ==================================================================

    @Slot(str, str, result=str)
    def generate_diff(self, path_a: str, path_b: str) -> str:
        import base

        name = f"diff_{abs(hash((path_a, path_b))) & 0xFFFFFFFF:08x}.png"
        out = os.path.join(self._diff_dir, name)
        try:
            result = base.similarity.diff_mask(path_a, path_b, out, tolerance=12)
        except Exception as e:
            logger.warning("diff_mask failed: %s", e)
            return ""
        if not result["ok"]:
            return ""
        self.diff_ready.emit(result["out_path"], result["changed_ratio"])
        return result["out_path"]

    # ==================================================================
    # Consolidation (hardlink/symlink)
    # ==================================================================

    @Slot(str)
    def consolidate_selected(self, mode: str = "auto"):
        total_linked, total_bytes, errors = 0, 0, []
        for c in self._cluster_model.clusters():
            selected_in_cluster = [p for p in c["paths"] if p in self.selected_files]
            if not selected_in_cluster:
                continue
            keeper = c.get("keeper") or ""
            if not keeper or keeper in selected_in_cluster:
                keeper, _ = auto_select(
                    [p for p in c["paths"] if p not in selected_in_cluster] or c["paths"],
                    self._triage_rules, self._ref_set,
                )
            if not keeper:
                continue
            res = consolidate_cluster(keeper, selected_in_cluster, mode=mode)
            total_linked += len(res.linked)
            total_bytes += res.bytes_reclaimed
            errors.extend(res.errors)
            self._deselect_paths(res.linked)
        self.on_selection_changed()
        summary = (f"Consolidated {total_linked} files "
                   f"({total_bytes / (1024 * 1024):.1f} MB reclaimed)")
        if errors:
            summary += f"; {len(errors)} errors (see log)"
            for e in errors[:10]:
                logger.warning("Consolidation error: %s", e)
        self.consolidation_done.emit(summary)
        self.status_label.setText(summary)
        self.scan_status_changed.emit(summary)

    # ==================================================================
    # Standard deletion (files + directory)
    # ==================================================================

    def delete_selected_duplicates(self):
        if not self.selected_files:
            return
        count = len(self.selected_files)
        prefs = self._prefs()
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"
        if self.confirm_checkbox.isChecked():
            reply = QMessageBox.question(
                self, "Confirm Batch Delete",
                f"Move **{count}** selected files to {action_name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        deleted_count = 0
        errors = []
        for path in list(self.selected_files):
            try:
                if send_to_trash_enabled:
                    send2trash(path)
                else:
                    os.remove(path)
                deleted_count += 1
                if path in self.selected_files:
                    self.selected_files.remove(path)
                if path in self.found_files:
                    self.found_files.remove(path)
                if path in self.path_to_label_map:
                    self.path_to_label_map.pop(path).deleteLater()
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {str(e)}")
        self.common_reflow_layout(self.found_gallery_layout, self._current_found_cols)
        self.refresh_selected_panel()
        self.on_selection_changed()
        msg = f"Moved {deleted_count} files to {action_name}."
        if errors:
            msg += "\nErrors:\n" + "\n".join(errors[:5])
        QMessageBox.information(self, f"Move to {action_name} Complete", msg)

    @Slot()
    def delete_selected_files_qml(self):
        self.delete_selected_duplicates()

    def delete_single_file(self, path: str):
        filename = os.path.basename(path)
        prefs = self._prefs()
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"
        reply = QMessageBox.question(
            self, "Confirm Deletion", f"Move to {action_name}:\n{filename}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return
        try:
            if send_to_trash_enabled:
                send2trash(path)
            else:
                os.remove(path)
            if path in self.selected_files:
                self.selected_files.remove(path)
            if path in self.found_files:
                self.found_files.remove(path)
            if path in self.path_to_label_map:
                self.path_to_label_map.pop(path).deleteLater()
            self.common_reflow_layout(self.found_gallery_layout, self._current_found_cols)
            self.refresh_selected_panel()
            self.on_selection_changed()
            self.status_label.setText(f"Moved to {action_name}: {filename}")
            QMessageBox.information(self, f"Moved to {action_name}", f"Moved to {action_name}: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Deletion Failed", f"Error: {e}")

    def start_deletion(self, mode: str):
        if not self.is_valid(mode):
            return
        config = self.collect(mode)
        config["require_confirm"] = self.confirm_checkbox.isChecked()
        self.btn_delete_files.setEnabled(False)
        self.btn_delete_directory.setEnabled(False)
        self.status_label.setText(f"Starting {mode} deletion...")
        QApplication.processEvents()
        self.worker = DeletionWorker(config)
        self.worker.confirm_signal.connect(self.handle_confirmation_request)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_deletion_done)
        self.worker.error.connect(self.on_deletion_error)
        self.worker.start()

    @Slot(bool)
    def set_require_confirm(self, value: bool):
        self.confirm_checkbox.setChecked(bool(value))

    @Slot(str)
    def delete_directory_qml(self, target_dir=""):
        if target_dir:
            self.target_path.setText(target_dir)
        self.start_deletion(mode="directory")

    @Slot(str, result="QStringList")
    def list_directory_qml(self, target_dir):
        """List all supported files in a directory for the QML gallery."""
        if not target_dir or not os.path.isdir(target_dir):
            return []
        self.target_path.setText(target_dir)
        self._list_all_files(target_dir, self._current_extensions())
        return [p for paths in self.duplicate_results.values() for p in paths]

    @Slot(str, int)
    def handle_confirmation_request(self, message: str, total_items: int):
        title = ("Confirm Directory Deletion"
                 if total_items == 1 and "directory" in message
                 else "Confirm File Deletion")
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        self.worker.set_confirmation_response(reply == QMessageBox.StandardButton.Yes)

    def update_progress(self, deleted, total):
        self.status_label.setText(f"Deleted {deleted} of {total}...")

    def on_deletion_done(self, count, msg):
        self.btn_delete_files.setEnabled(len(self.selected_files) > 0)
        self.btn_delete_directory.setEnabled(True)
        self.status_label.setText(msg)
        QMessageBox.information(self, "Complete", msg)
        self.worker = None

    def on_deletion_error(self, msg):
        self.btn_delete_files.setEnabled(True)
        self.btn_delete_directory.setEnabled(True)
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)
        self.worker = None

    # ==================================================================
    # Properties / previews / context menus (from DeleteTab)
    # ==================================================================

    def _prefs(self) -> dict:
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            return main_win.cached_creds.get("preferences", {})
        return {}

    def get_image_properties(self, file_path: str) -> Dict[str, Any]:
        if not Path(file_path).exists():
            return {"Error": "File not found."}
        props: Dict[str, Any] = {"Path": file_path, "File Name": os.path.basename(file_path)}
        try:
            stat = os.stat(file_path)
            props["File Size"] = f"{stat.st_size / (1024 * 1024):.2f} MB ({stat.st_size} bytes)"
            props["Last Modified"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            props["File Size"] = "N/A"
        try:
            img = Image.open(file_path)
            props["Width"] = f"{img.width} px"
            props["Height"] = f"{img.height} px"
            props["Format"] = img.format
            img.close()
        except Exception:
            props["Width"] = "N/A"
        return props

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        prop_action = QAction("🖼️ Show Image Properties", self)
        prop_action.triggered.connect(lambda: self.show_image_properties_dialog(path))
        menu.addAction(prop_action)
        if len(self.selected_files) > 1:
            cmp_action = QAction("📊 Compare Selected Properties", self)
            cmp_action.triggered.connect(self.show_comparison_dialog)
            menu.addAction(cmp_action)
        menu.addSeparator()
        view_action = QAction("🔍 View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.open_full_preview(path))
        menu.addAction(view_action)
        is_selected = path in self.selected_files
        toggle_text = "Deselect (Keep)" if is_selected else "Select (Mark for Delete)"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)
        menu.addSeparator()
        delete_action = QAction("🗑️ Delete This File", self)
        delete_action.triggered.connect(lambda: self.delete_single_file(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    @Slot(str)
    def show_image_properties_dialog(self, path: str):
        properties = self.get_image_properties(path)
        if "Error" in properties:
            QMessageBox.critical(self, "Error Reading File", properties["Error"])
            return
        prop_text = f"**File:** {os.path.basename(path)}\n**Path:** {path}\n\n**Technical Details**\n"
        for key, value in properties.items():
            if key not in ["Path", "File Name"]:
                prop_text += f"  - **{key}:** {value}\n"
        msg = QMessageBox(self)
        msg.setWindowTitle("Image Properties")
        msg.setTextFormat(Qt.TextFormat.MarkdownText)
        msg.setText(prop_text)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()

    @Slot()
    def show_comparison_dialog(self):
        if not self.selected_files:
            QMessageBox.warning(self, "No Selection", "Please select at least one image to compare.")
            return
        selected_paths = list(self.selected_files)
        if len(selected_paths) > 10:
            reply = QMessageBox.question(
                self, "Large Selection",
                f"Selected {len(selected_paths)} images. Compare first 10?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                selected_paths = selected_paths[:10]
            else:
                return
        property_list = []
        for path in selected_paths:
            if Path(path).exists():
                property_list.append(self.get_image_properties(path))
            else:
                property_list.append({"File Name": os.path.basename(path), "Path": path,
                                      "Error": "File not found."})
        dialog = PropertyComparisonDialog(property_list, self)
        dialog.exec()

    def open_full_preview(self, image_path: str):
        full_list = self.found_files
        target_list = full_list if full_list else list(self.selected_files)
        if not target_list:
            target_list = [image_path]
        elif image_path not in target_list:
            target_list.append(image_path)
        try:
            start_index = target_list.index(image_path)
        except ValueError:
            start_index = 0
        preview = ImagePreviewWindow(image_path=image_path, db_tab_ref=None, parent=self,
                                     all_paths=target_list, start_index=start_index)
        preview.path_changed.connect(self.update_preview_highlight)
        preview.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        preview.show()
        self.open_preview_windows.append(preview)

    # ==================================================================
    # Extensions + validation + config
    # ==================================================================

    def browse_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Select Directory", self.last_browsed_dir)
        if d:
            self.target_path.setText(d)
            self.last_browsed_dir = d
            self.start_duplicate_scan()

    @Slot(str)
    def browse_target_qml(self, current_path=""):
        starting_dir = current_path if os.path.isdir(current_path) else ""
        d = QFileDialog.getExistingDirectory(self, "Select Directory to Scan", starting_dir)
        if d:
            self.target_path.setText(d)
            self.qml_input_path_changed.emit(d)
            return d
        return ""

    def is_valid(self, mode: str):
        p = self.target_path.text().strip()
        if not p or not os.path.exists(p):
            QMessageBox.warning(self, "Invalid", "Select valid file/folder.")
            return False
        if mode == "directory" and not os.path.isdir(p):
            QMessageBox.warning(self, "Invalid", "Directory required.")
            return False
        return True

    def toggle_extension(self, ext, checked):
        btn = self.extension_buttons[ext]
        if checked:
            self.selected_extensions.add(ext)
            btn.setStyleSheet("QPushButton:checked { background-color: #3320b5; color: white; }")
            apply_shadow_effect(btn, "#000000", 8, 0, 3)
        else:
            self.selected_extensions.discard(ext)
            btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
            apply_shadow_effect(btn, "#000000", 8, 0, 3)

    def add_all_extensions(self):
        for ext, btn in self.extension_buttons.items():
            btn.setChecked(True)
            self.toggle_extension(ext, True)

    def remove_all_extensions(self):
        for ext, btn in self.extension_buttons.items():
            btn.setChecked(False)
            self.toggle_extension(ext, False)

    def collect(self, mode: str = "files") -> Dict[str, Any]:
        exts = []
        if self.dropdown and self.selected_extensions is not None:
            exts = list(self.selected_extensions)
        elif not self.dropdown and hasattr(self, "target_extensions"):
            exts = self.join_list_str(self.target_extensions.text().strip())
        send_to_trash_enabled = self._prefs().get("send_to_trash", True)
        return {
            "target_path": self.target_path.text().strip(),
            "mode": mode,
            "target_extensions": [e.strip().lstrip(".") for e in exts if e.strip()],
            "scan_method": self.scan_method_combo.currentText(),
            "require_confirm": self.confirm_checkbox.isChecked(),
            "selected_files": list(self.selected_files),
            "send_to_trash": send_to_trash_enabled,
            "similarity": self._sim_config.to_dict(),
            "triage": self._triage_rules.to_dict(),
        }

    @staticmethod
    def join_list_str(text: str):
        return [item.strip().lstrip(".")
                for item in text.replace(",", " ").split() if item.strip()]

    def get_default_config(self) -> dict:
        extensions = SUPPORTED_IMG_FORMATS if self.dropdown else "jpg png"
        return {
            "target_path": "",
            "scan_method": "Similarity Engine (tiered clusters)",
            "target_extensions": extensions,
            "require_confirm": True,
            "similarity": SimilarityConfig().to_dict(),
            "triage": TriageRules().to_dict(),
        }

    def set_config(self, config: dict):
        try:
            self.target_path.setText(config.get("target_path", ""))
            scan_method = config.get("scan_method", "Similarity Engine (tiered clusters)")
            index = self.scan_method_combo.findText(scan_method)
            if index != -1:
                self.scan_method_combo.setCurrentIndex(index)
            extensions = config.get("target_extensions", [])
            if self.dropdown:
                self.remove_all_extensions()
                for ext in extensions:
                    if ext in self.extension_buttons:
                        self.extension_buttons[ext].setChecked(True)
                        self.toggle_extension(ext, True)
                if extensions and len(extensions) < len(SUPPORTED_IMG_FORMATS):
                    self.extensions_field.set_open(True)
            elif hasattr(self, "target_extensions"):
                self.target_extensions.setText(" ".join(extensions))
                if extensions:
                    self.extensions_field.set_open(True)
            self.confirm_checkbox.setChecked(config.get("require_confirm", True))
            self._restore_selected_files(config)
            if config.get("similarity"):
                self._sim_config = SimilarityConfig.from_dict(config["similarity"])
            if config.get("triage"):
                self._triage_rules = TriageRules.from_dict(config["triage"])
        except Exception as e:
            logger.error("Error applying SimilarityTab config: %s", e)
            QMessageBox.warning(self, "Config Error", f"Failed to apply some settings: {e}")

    # ==================================================================
    # Lifecycle
    # ==================================================================

    def cancel_loading(self):
        thread = getattr(self, "_sim_thread", None)
        if thread and thread.isRunning():
            thread.requestInterruption()
            thread.quit()
            thread.wait(2000)
        with contextlib.suppress(Exception):
            super().cancel_loading()
        if self.worker:
            with contextlib.suppress(Exception):
                if hasattr(self.worker, "stop"):
                    self.worker.stop()
        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        self.cancel_loading()
        super().closeEvent(event)
