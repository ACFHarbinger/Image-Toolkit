"""Metadata Editor Window — launched when the user clicks Add/Update N Selected Images.

Layout
------
  Tab 0 : "Batch / Overview"  — set metadata for all images at once, or define
           named *clusters* (subsets of images) each with their own config.
           A pattern-mode fills sequential fields (name1, name2 …) automatically.
  Tab 1…N : one tab per selected image, showing a small thumbnail + individual
             editable fields whose values start pre-filled from the Batch tab.

On "Confirm and Save" the caller receives a list of per-image dicts via the
``metadata_confirmed`` signal so ``ScanMetadataTab`` can do the actual DB
writes without importing Qt.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..styles import apply_shadow_effect

# ---------------------------------------------------------------------------
# Tag colour palette (mirrors scan_metadata_tab)
# ---------------------------------------------------------------------------
_TAG_COLORS: Dict[str, str] = {
    "Artist": "#5865f2",
    "Series": "#f1c40f",
    "Character": "#2ecc71",
    "General": "#e91e63",
    "Meta": "#9b59b6",
    "": "#c7c7c7",
}

_LIST_STYLE = (
    "QListWidget::item { padding: 4px; } "
    "QListWidget { background-color: #2c2f33; border: 1px solid #4f545c; border-radius: 6px; }"
)
_INPUT_STYLE = (
    "QLineEdit, QComboBox { background-color: #2c2f33; color: #dcddde; "
    "border: 1px solid #4f545c; border-radius: 4px; padding: 4px; }"
)
_GROUP_STYLE = (
    "QGroupBox { font-weight: bold; border: 1px solid #4f545c; border-radius: 6px; "
    "margin-top: 8px; padding-top: 8px; } "
    "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FilteredTagList(QWidget):
    """A widget wrapping a QListWidget and horizontal checkboxes to filter by tag type."""
    def __init__(self, tags_data: List[Dict[str, str]], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._tags_data = tags_data

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Master checkbox toggle for filtering
        self.master_filter_layout = QHBoxLayout()
        self.master_filter_layout.setSpacing(10)
        self.master_cb = QCheckBox("Filter by Type")
        self.master_cb.setChecked(False)
        self.master_cb.stateChanged.connect(self._toggle_filter_visibility)
        self.master_filter_layout.addWidget(self.master_cb)

        # Container for the individual type checkboxes
        self.type_container = QWidget()
        self.type_layout = QHBoxLayout(self.type_container)
        self.type_layout.setContentsMargins(0, 0, 0, 0)
        self.type_layout.setSpacing(10)

        self.checkboxes: Dict[str, QCheckBox] = {}
        # Order the types: Artist, Series, Character, General, Meta, then others, then empty/Other
        standard_types = ["Artist", "Series", "Character", "General", "Meta"]
        all_types = []
        for t in standard_types:
            if any((td.get("type") or "") == t for td in tags_data):
                all_types.append(t)
        # Check for others
        for td in tags_data:
            t = td.get("type") or ""
            if t not in all_types and t != "":
                all_types.append(t)
        # Empty/uncategorized type
        if any((td.get("type") or "") == "" for td in tags_data):
            all_types.append("")

        for t in all_types:
            label = t if t != "" else "Other"
            cb = QCheckBox(label)
            color = _TAG_COLORS.get(t, _TAG_COLORS[""])
            cb.setStyleSheet(f"color: {color}; font-weight: bold;")
            cb.setChecked(True)
            cb.stateChanged.connect(self._apply_filter)
            self.type_layout.addWidget(cb)
            self.checkboxes[t] = cb

        self.master_filter_layout.addWidget(self.type_container)
        self.master_filter_layout.addStretch()
        layout.addLayout(self.master_filter_layout)

        # List widget
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(160)
        self.list_widget.setStyleSheet(_LIST_STYLE)

        self._all_items: List[Tuple[QListWidgetItem, str]] = []
        for td in tags_data:
            name = td["name"]
            ttype = td.get("type") or ""
            item = QListWidgetItem(name.replace("_", " ").title())
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setForeground(QColor(_TAG_COLORS.get(ttype, _TAG_COLORS[""])))
            self.list_widget.addItem(item)
            self._all_items.append((item, ttype))

        layout.addWidget(self.list_widget)

        # Initial visibility toggle
        self._toggle_filter_visibility()

    def _toggle_filter_visibility(self) -> None:
        self.type_container.setVisible(self.master_cb.isChecked())
        self._apply_filter()

    def _apply_filter(self) -> None:
        filter_enabled = self.master_cb.isChecked()
        for item, ttype in self._all_items:
            if not filter_enabled:
                item.setHidden(False)
            else:
                cb = self.checkboxes.get(ttype)
                visible = cb.isChecked() if cb else True
                item.setHidden(not visible)

    def checked_tags(self) -> List[str]:
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item, _ in self._all_items
            if item.checkState() == Qt.CheckState.Checked
        ]

    def set_checked_tags(self, tags: List[str]) -> None:
        tag_set = set(tags)
        for item, _ in self._all_items:
            item.setCheckState(
                Qt.CheckState.Checked
                if item.data(Qt.ItemDataRole.UserRole) in tag_set
                else Qt.CheckState.Unchecked
            )


def _make_tag_list(tags_data: List[Dict[str, str]]) -> FilteredTagList:
    """Return a FilteredTagList pre-populated with checkable tag items."""
    return FilteredTagList(tags_data)


def _checked_tags(lw: FilteredTagList | QListWidget) -> List[str]:
    if hasattr(lw, "checked_tags"):
        return lw.checked_tags()
    return [
        lw.item(i).data(Qt.ItemDataRole.UserRole) # pyrefly: ignore [missing-attribute]
        for i in range(lw.count()) # pyrefly: ignore [missing-attribute]
        if lw.item(i).checkState() == Qt.CheckState.Checked # pyrefly: ignore [missing-attribute]
    ]


def _set_checked_tags(lw: FilteredTagList | QListWidget, tags: List[str]) -> None:
    if hasattr(lw, "set_checked_tags"):
        lw.set_checked_tags(tags)
        return
    tag_set = set(tags)
    for i in range(lw.count()): # pyrefly: ignore [missing-attribute]
        item = lw.item(i) # pyrefly: ignore [missing-attribute]
        item.setCheckState(
            Qt.CheckState.Checked
            if item.data(Qt.ItemDataRole.UserRole) in tag_set
            else Qt.CheckState.Unchecked
        )


def _apply_pattern(template: str, index: int) -> str:
    """Replace {n} or trailing digits with sequential index.

    Examples:
        "name{n}"  → "name1", "name2", …
        "shot"     → "shot1", "shot2", …  (auto-append)
    """
    if "{n}" in template:
        return template.replace("{n}", str(index + 1))
    return f"{template}{index + 1}"


def _thumb(path: str, size: int = 120) -> QLabel:
    lbl = QLabel()
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("border: 1px solid #4f545c; background-color: #1e2124; border-radius: 4px;")
    px = QPixmap(path)
    if not px.isNull():
        lbl.setPixmap(px.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation))
    else:
        lbl.setText("?")
    return lbl


# ---------------------------------------------------------------------------
# Cluster entry (used by the Batch tab)
# ---------------------------------------------------------------------------

class _ClusterEntry(QGroupBox):
    """One cluster: a label, an image-path selection list, and a metadata form."""

    remove_requested = Signal(object)  # emits self

    def __init__(
        self,
        index: int,
        all_paths: List[str],
        groups: List[str],
        subgroups: List[Tuple[str, str]],
        tags_data: List[Dict[str, str]],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(f"Cluster {index + 1}", parent)
        self.setStyleSheet(_GROUP_STYLE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._all_paths = all_paths

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 16, 8, 8)

        # Header row: rename + remove
        hdr = QHBoxLayout()
        self._name_edit = QLineEdit(f"Cluster {index + 1}")
        self._name_edit.setStyleSheet(_INPUT_STYLE)
        self._name_edit.textChanged.connect(lambda t: self.setTitle(t or f"Cluster {index + 1}"))
        hdr.addWidget(QLabel("Name:"))
        hdr.addWidget(self._name_edit, 1)
        btn_remove = QPushButton("✕ Remove")
        btn_remove.setStyleSheet("background-color: #992222; color: white; padding: 4px 8px;")
        btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))
        hdr.addWidget(btn_remove)
        root.addLayout(hdr)

        # Image multi-selection
        img_lbl = QLabel("Images in this cluster (check to include):")
        root.addWidget(img_lbl)
        self._img_list = QListWidget()
        self._img_list.setMaximumHeight(110)
        self._img_list.setStyleSheet(_LIST_STYLE)
        for p in all_paths:
            item = QListWidgetItem(os.path.basename(p))
            item.setData(Qt.ItemDataRole.UserRole, p)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._img_list.addItem(item)
        root.addWidget(self._img_list)

        btn_row = QHBoxLayout()
        for label, state in [("Check All", Qt.CheckState.Checked), ("Uncheck All", Qt.CheckState.Unchecked)]:
            b = QPushButton(label)
            b.setStyleSheet("padding: 3px 8px;")
            s = state
            b.clicked.connect(lambda _, st=s: self._set_all(st))
            btn_row.addWidget(b)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Metadata form
        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)

        self._group_combo = QComboBox()
        self._group_combo.setEditable(True)
        self._group_combo.setPlaceholderText("Group…")
        self._group_combo.addItems([""] + groups)
        self._group_combo.setStyleSheet(_INPUT_STYLE)
        self._group_combo.currentTextChanged.connect(self._refresh_subgroups)
        form.addRow("Group:", self._group_combo)

        self._subgroup_combo = QComboBox()
        self._subgroup_combo.setEditable(True)
        self._subgroup_combo.setPlaceholderText("Subgroup…")
        self._subgroup_combo.setStyleSheet(_INPUT_STYLE)
        self._all_subgroups = subgroups  # list of (subgroup_name, group_name)
        self._refresh_subgroups()
        form.addRow("Subgroup:", self._subgroup_combo)

        # Pattern mode
        pat_row = QHBoxLayout()
        self._pattern_check = QCheckBox("Group pattern (sequential)")
        self._pattern_check.setToolTip(
            "When checked, the Group/Subgroup values are treated as templates.\n"
            "Use {n} for the index, or leave it out to auto-append a number.\n"
            "e.g. 'Episode{n}' → Episode1, Episode2…"
        )
        pat_row.addWidget(self._pattern_check)
        pat_row.addStretch()
        root.addLayout(pat_row)

        self._tags_lw = _make_tag_list(tags_data)
        form.addRow("Tags:", self._tags_lw)
        root.addLayout(form)

    # ------------------------------------------------------------------
    def _set_all(self, state: Qt.CheckState) -> None:
        for i in range(self._img_list.count()):
            self._img_list.item(i).setCheckState(state)

    def _refresh_subgroups(self) -> None:
        grp = self._group_combo.currentText().strip()
        self._subgroup_combo.clear()
        self._subgroup_combo.addItem("")
        for sg, g in self._all_subgroups:
            if not grp or g.lower() == grp.lower():
                self._subgroup_combo.addItem(sg)

    # ------------------------------------------------------------------
    def checked_paths(self) -> List[str]:
        return [
            self._img_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._img_list.count())
            if self._img_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def metadata_for(self, path: str) -> Dict[str, Any]:
        """Return the metadata dict for a specific path in this cluster."""
        grp_tmpl = self._group_combo.currentText().strip() or None
        sub_tmpl = self._subgroup_combo.currentText().strip() or None
        tags = _checked_tags(self._tags_lw)
        use_pattern = self._pattern_check.isChecked()

        checked = self.checked_paths()
        idx = checked.index(path) if path in checked else 0

        grp = _apply_pattern(grp_tmpl, idx) if (use_pattern and grp_tmpl) else grp_tmpl
        sub = _apply_pattern(sub_tmpl, idx) if (use_pattern and sub_tmpl) else sub_tmpl
        return {"group_name": grp, "subgroup_name": sub, "tags": tags or None}


# ---------------------------------------------------------------------------
# Per-image tab widget
# ---------------------------------------------------------------------------

class _ImageTab(QWidget):
    """A single tab showing a thumbnail and editable metadata for one image."""

    def __init__(
        self,
        path: str,
        groups: List[str],
        subgroups: List[Tuple[str, str]],
        tags_data: List[Dict[str, str]],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.path = path
        self._all_subgroups = subgroups

        root = QHBoxLayout(self)

        # Left: thumbnail
        left = QVBoxLayout()
        left.setAlignment(Qt.AlignmentFlag.AlignTop)
        left.addWidget(_thumb(path, 140))
        fn_lbl = QLabel(os.path.basename(path))
        fn_lbl.setWordWrap(True)
        fn_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        fn_lbl.setMaximumWidth(150)
        left.addWidget(fn_lbl)
        left.addStretch()
        root.addLayout(left)

        # Right: form
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(8, 4, 4, 4)

        self._group_combo = QComboBox()
        self._group_combo.setEditable(True)
        self._group_combo.setPlaceholderText("Group…")
        self._group_combo.addItems([""] + groups)
        self._group_combo.setStyleSheet(_INPUT_STYLE)
        self._group_combo.currentTextChanged.connect(self._refresh_subgroups)
        form.addRow("Group:", self._group_combo)

        self._subgroup_combo = QComboBox()
        self._subgroup_combo.setEditable(True)
        self._subgroup_combo.setPlaceholderText("Subgroup…")
        self._subgroup_combo.setStyleSheet(_INPUT_STYLE)
        self._refresh_subgroups()
        form.addRow("Subgroup:", self._subgroup_combo)

        self._tags_lw = _make_tag_list(tags_data)
        form.addRow("Tags:", self._tags_lw)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_widget)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        root.addWidget(scroll, 1)

    def _refresh_subgroups(self) -> None:
        grp = self._group_combo.currentText().strip()
        self._subgroup_combo.clear()
        self._subgroup_combo.addItem("")
        for sg, g in self._all_subgroups:
            if not grp or g.lower() == grp.lower():
                self._subgroup_combo.addItem(sg)

    def apply_batch(self, meta: Dict[str, Any]) -> None:
        """Pre-fill this tab's fields from a batch-level dict."""
        if meta.get("group_name"):
            self._group_combo.setCurrentText(meta["group_name"])
        if meta.get("subgroup_name"):
            self._subgroup_combo.setCurrentText(meta["subgroup_name"])
        if meta.get("tags"):
            _set_checked_tags(self._tags_lw, meta["tags"])

    def collect(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "group_name": self._group_combo.currentText().strip() or None,
            "subgroup_name": self._subgroup_combo.currentText().strip() or None,
            "tags": _checked_tags(self._tags_lw) or None,
        }


# ---------------------------------------------------------------------------
# Batch tab
# ---------------------------------------------------------------------------

class _BatchTab(QWidget):
    """The first tab — bulk-apply metadata and define clusters."""

    def __init__(
        self,
        all_paths: List[str],
        groups: List[str],
        subgroups: List[Tuple[str, str]],
        tags_data: List[Dict[str, str]],
        per_image_tabs: List["_ImageTab"],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._all_paths = all_paths
        self._groups = groups
        self._subgroups = subgroups
        self._tags_data = tags_data
        self._per_image_tabs = per_image_tabs
        self._clusters: List[_ClusterEntry] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        # --- Apply-to-all section ---
        all_box = QGroupBox("Apply to ALL Images")
        all_box.setStyleSheet(_GROUP_STYLE)
        all_form = QFormLayout(all_box)
        all_form.setContentsMargins(8, 16, 8, 8)

        self._all_group = QComboBox()
        self._all_group.setEditable(True)
        self._all_group.setPlaceholderText("Group…")
        self._all_group.addItems([""] + groups)
        self._all_group.setStyleSheet(_INPUT_STYLE)
        self._all_group.currentTextChanged.connect(self._refresh_all_subgroups)
        all_form.addRow("Group:", self._all_group)

        self._all_subgroup = QComboBox()
        self._all_subgroup.setEditable(True)
        self._all_subgroup.setPlaceholderText("Subgroup…")
        self._all_subgroup.setStyleSheet(_INPUT_STYLE)
        self._refresh_all_subgroups()
        all_form.addRow("Subgroup:", self._all_subgroup)

        self._all_tags = _make_tag_list(tags_data)
        all_form.addRow("Tags:", self._all_tags)

        apply_all_btn = QPushButton("⬇  Apply to All Image Tabs")
        apply_all_btn.setStyleSheet(
            "QPushButton { background: #5865f2; color: white; font-weight: bold; "
            "padding: 8px 14px; border-radius: 6px; }"
            "QPushButton:hover { background: #4752c4; }"
        )
        apply_shadow_effect(apply_all_btn, "#000000", 6, 0, 2)
        apply_all_btn.clicked.connect(self._apply_all)
        all_form.addRow("", apply_all_btn)
        root.addWidget(all_box)

        # --- Clusters ---
        clusters_hdr = QHBoxLayout()
        clusters_hdr.addWidget(QLabel("Clusters (optional — override specific image subsets):"))
        clusters_hdr.addStretch()
        add_cluster_btn = QPushButton("+ Add Cluster")
        add_cluster_btn.setStyleSheet(
            "QPushButton { background: #2ecc71; color: white; padding: 5px 12px; border-radius: 5px; }"
            "QPushButton:hover { background: #27ae60; }"
        )
        add_cluster_btn.clicked.connect(self._add_cluster)
        clusters_hdr.addWidget(add_cluster_btn)
        root.addLayout(clusters_hdr)

        apply_clusters_btn = QPushButton("⬇  Apply All Clusters to Image Tabs")
        apply_clusters_btn.setStyleSheet(
            "QPushButton { background: #e67e22; color: white; font-weight: bold; "
            "padding: 7px 14px; border-radius: 6px; }"
            "QPushButton:hover { background: #ca6f1e; }"
        )
        apply_shadow_effect(apply_clusters_btn, "#000000", 6, 0, 2)
        apply_clusters_btn.clicked.connect(self._apply_clusters)
        root.addWidget(apply_clusters_btn)

        # Scrollable cluster container
        self._cluster_container = QWidget()
        self._cluster_layout = QVBoxLayout(self._cluster_container)
        self._cluster_layout.setContentsMargins(0, 0, 0, 0)
        self._cluster_layout.setSpacing(8)
        self._cluster_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._cluster_container)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; border-radius: 6px; }")
        root.addWidget(scroll, 1)

    # ------------------------------------------------------------------ helpers

    def _refresh_all_subgroups(self) -> None:
        grp = self._all_group.currentText().strip()
        self._all_subgroup.clear()
        self._all_subgroup.addItem("")
        for sg, g in self._subgroups:
            if not grp or g.lower() == grp.lower():
                self._all_subgroup.addItem(sg)

    def _apply_all(self) -> None:
        meta = {
            "group_name": self._all_group.currentText().strip() or None,
            "subgroup_name": self._all_subgroup.currentText().strip() or None,
            "tags": _checked_tags(self._all_tags),
        }
        for tab in self._per_image_tabs:
            tab.apply_batch(meta)

    def _add_cluster(self) -> None:
        idx = len(self._clusters)
        cluster = _ClusterEntry(
            idx, self._all_paths, self._groups, self._subgroups, self._tags_data
        )
        cluster.remove_requested.connect(self._remove_cluster)
        self._clusters.append(cluster)
        # Insert before the trailing stretch
        self._cluster_layout.insertWidget(self._cluster_layout.count() - 1, cluster)

    def _remove_cluster(self, cluster: _ClusterEntry) -> None:
        self._clusters.remove(cluster)
        self._cluster_layout.removeWidget(cluster)
        cluster.deleteLater()

    def _apply_clusters(self) -> None:
        for cluster in self._clusters:
            paths = cluster.checked_paths()
            for path in paths:
                meta = cluster.metadata_for(path)
                for tab in self._per_image_tabs:
                    if tab.path == path:
                        tab.apply_batch(meta)


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

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
        self._paths = list(selected_paths)

        # ---- Fetch DB data ----
        groups: List[str] = []
        subgroups: List[Tuple[str, str]] = []
        tags_data: List[Dict[str, str]] = []
        try:
            groups = db.get_all_groups() or []
            subgroups = db.get_all_subgroups_detailed() or []
            tags_data = db.get_all_tags_with_types() or []
        except Exception:
            pass

        # ---- Build per-image tabs first (batch tab references them) ----
        self._image_tabs: List[_ImageTab] = [
            _ImageTab(p, groups, subgroups, tags_data) for p in self._paths
        ]

        # ---- Tab widget ----
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            "QTabBar::tab { min-width: 110px; padding: 6px 10px; }"
            "QTabBar::tab:selected { background: #5865f2; color: white; border-radius: 4px; }"
        )

        # Batch tab
        batch_tab = _BatchTab(
            self._paths, groups, subgroups, tags_data, self._image_tabs
        )
        self._tabs.addTab(batch_tab, "📋 Batch / Overview")

        # Per-image tabs
        for i, (tab, path) in enumerate(zip(self._image_tabs, self._paths)):
            label = os.path.basename(path)
            # Truncate long filenames in the tab bar
            if len(label) > 20:
                label = label[:17] + "…"
            self._tabs.addTab(tab, f"🖼 {label}")

        # ---- Footer buttons ----
        btn_cancel = QPushButton("✕ Cancel")
        btn_cancel.setStyleSheet(
            "QPushButton { background: #4f545c; color: white; padding: 9px 18px; "
            "border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #686d73; }"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_confirm = QPushButton(f"✔ Confirm and Save {len(self._paths)} Image(s)")
        btn_confirm.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #2ecc71,stop:1 #27ae60); color: white; padding: 9px 18px; "
            "border-radius: 6px; font-weight: bold; font-size: 14px; }"
            "QPushButton:hover { background: #27ae60; }"
            "QPushButton:pressed { background: #1e8449; }"
        )
        apply_shadow_effect(btn_confirm, "#000000", 8, 0, 3)
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
