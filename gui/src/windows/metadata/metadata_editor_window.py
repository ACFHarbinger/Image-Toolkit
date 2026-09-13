"""``MetadataEditorWindow`` -- the tabbed metadata-editing dialog."""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTabWidget, QVBoxLayout, QWidget

from gui.src.theming.theme_api import qss

from ...styles import apply_shadow_effect
from ..window_manager import register_window
from ._batch_tab import _BatchTab
from ._image_tab import _ImageTab

logger = logging.getLogger(__name__)

class MetadataEditorWindow(QDialog):
    """Tabbed dialog for editing metadata across selected images before saving."""

    # Emitted on Confirm; payload: list of per-image metadata dicts
    metadata_confirmed = Signal(list)

    def __init__(
        self,
        selected_paths: List[str],
        db,  # UnifiedImageDatabase or compatible
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Metadata — {len(selected_paths)} Image(s)")
        self.setMinimumSize(900, 680)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        register_window(self)
        self._paths = list(selected_paths)

        # ---- Fetch DB data ----
        groups: List[str] = []
        subgroups: List[Tuple[str, str]] = []
        tags_data: List[Dict[str, str]] = []
        try:
            groups = db.get_all_groups() or []
            subgroups = db.get_all_subgroups_detailed() or []
            tags_data = db.get_all_tags_with_categories() or []
        except Exception:
            logger.debug("Suppressed Exception in MetadataEditorWindow.__init__", exc_info=True)

        # ---- Build per-image tabs first (batch tab references them) ----
        self._image_tabs: List[_ImageTab] = [
            _ImageTab(p, groups, subgroups, tags_data) for p in self._paths
        ]

        # ---- Tab widget ----
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(qss("metadata_editor_tabs"))

        # Batch tab
        batch_tab = _BatchTab(
            self._paths, groups, subgroups, tags_data, self._image_tabs
        )
        self._tabs.addTab(batch_tab, "📋 Batch / Overview")

        # Per-image tabs
        for _i, (tab, path) in enumerate(zip(self._image_tabs, self._paths, strict=False)):
            label = os.path.basename(path)
            # Truncate long filenames in the tab bar
            if len(label) > 20:
                label = label[:17] + "…"
            self._tabs.addTab(tab, f"🖼 {label}")

        # ---- Footer buttons ----
        btn_cancel = QPushButton("✕ Cancel")
        btn_cancel.setStyleSheet(qss("metadata_btn_cancel"))
        btn_cancel.clicked.connect(self.reject)

        btn_confirm = QPushButton(f"✔ Confirm and Save {len(self._paths)} Image(s)")
        btn_confirm.setStyleSheet(qss("metadata_btn_confirm"))
        apply_shadow_effect(btn_confirm, "black", 8, 0, 3)
        btn_confirm.clicked.connect(self._confirm)

        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(btn_cancel)
        footer.addWidget(btn_confirm)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.addWidget(self._tabs, 1)
        root.addLayout(footer)

    # ------------------------------------------------------------------ slots

    def _confirm(self) -> None:
        results = [tab.collect() for tab in self._image_tabs]
        self.metadata_confirmed.emit(results)
        self.accept()


__all__ = ["MetadataEditorWindow"]
