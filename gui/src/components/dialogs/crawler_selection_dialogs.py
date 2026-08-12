import contextlib
import hashlib
import os
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from backend.src.core.dir_phash_index import compute_phash_file
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


# Helper for computing Hamming distance between two 64-bit integers
def _hamming64(a: int, b: int) -> int:
    return ((a ^ b) & 0xFFFFFFFFFFFFFFFF).bit_count()

# Helper to get file size string
def get_file_size_str(path: str) -> str:
    try:
        size_bytes = os.path.getsize(path)
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
    except Exception:
        return "Unknown size"

# Helper to compute exact file hash
def get_file_sha256(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


class ClickableImageCard(QFrame):
    """
    Interactive image card that toggles between KEEP (blue border/bg) and DISCARD (red border/bg) states when clicked anywhere.
    """
    def __init__(
        self,
        clean_path: str,
        raw_path: str,
        item: Union[str, dict],
        idx: int,
        parent_dialog=None,
    ):
        super().__init__(parent_dialog)
        self.clean_path = clean_path
        self.raw_path = raw_path
        self.item = item
        self.idx = idx
        self.parent_dialog = parent_dialog
        self.is_kept = True  # Default: Keep (Blue)

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if isinstance(item, dict):
            page_url = item.get("page_url", "")
            page_num = item.get("page_num", 1)
            index_on_page = item.get("index_on_page", idx + 1)
            global_id = item.get("global_id", idx + 1)
        else:
            page_url = ""
            page_num = 1
            index_on_page = idx + 1
            global_id = idx + 1

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(6)

        # Thumbnail Label
        thumb_label = QLabel()
        thumb_label.setFixedSize(160, 160)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = QPixmap(clean_path)
        if pixmap.isNull() and os.path.exists(clean_path):
            with contextlib.suppress(Exception):
                from PIL import Image, ImageQt

                pil_img = Image.open(clean_path)
                pil_img.thumbnail((150, 150))
                q_img = ImageQt.ImageQt(pil_img)
                pixmap = QPixmap.fromImage(q_img)

        if not pixmap.isNull():
            thumb_label.setPixmap(
                pixmap.scaled(
                    150,
                    150,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            thumb_label.setText("No Preview")
            thumb_label.setStyleSheet("color: #888888; font-style: italic;")

        # Metadata
        filename = os.path.basename(clean_path)
        if len(filename) > 20:
            filename = filename[:17] + "..."

        size_str = get_file_size_str(clean_path)
        meta_html = f"<b>{filename}</b> ({size_str})<br/>"
        meta_html += f"<span style='color: #00f0ff;'><b>Pos on Page: #{index_on_page}</b></span> &nbsp;|&nbsp; Page #{page_num}<br/>"
        meta_html += f"<span style='color: #a0a0a0;'>Global ID: #{global_id}</span>"

        if page_url:
            short_url = page_url.replace("https://", "").replace("http://", "")
            if len(short_url) > 26:
                short_url = short_url[:23] + "..."
            meta_html += f"<br/><span style='color: #888888;'>URL: {short_url}</span>"

        info_label = QLabel(meta_html)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setStyleSheet("font-size: 11px;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Status Badge Pill (KEEP vs DISCARD)
        self.status_badge = QLabel()
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_layout.addWidget(thumb_label, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(info_label, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignCenter)

        self.update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_kept(not self.is_kept)
        super().mousePressEvent(event)

    def set_kept(self, kept: bool):
        self.is_kept = kept
        self.update_style()

    def update_style(self):
        if self.is_kept:
            # KEEP State: Blue Edge (#00f0ff) and Dark Blue Background (#102a43)
            self.setStyleSheet(
                "QFrame { border: 2px solid #00f0ff; border-radius: 8px; background-color: #102a43; padding: 5px; }"
            )
            self.status_badge.setText("✓ KEEP (Selected)")
            self.status_badge.setStyleSheet(
                "background-color: #00f0ff; color: #0a0a0c; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 4px 10px;"
            )
        else:
            # NOT KEEP State: Red Edge (#ff3355) and Dark Red Background (#38131d)
            self.setStyleSheet(
                "QFrame { border: 2px solid #ff3355; border-radius: 8px; background-color: #38131d; padding: 5px; }"
            )
            self.status_badge.setText("✗ DISCARD (Will Delete)")
            self.status_badge.setStyleSheet(
                "background-color: #ff3355; color: #ffffff; font-weight: bold; font-size: 11px; border-radius: 4px; padding: 4px 10px;"
            )


class ManualSelectionDialog(QDialog):
    """
    Shows an interactive grid of downloaded images where clicking any card toggles between KEEP (blue) and DISCARD (red).
    Displays Page URL, Page #, and Pos # on Page (counter ID) to assist with Skip First/Last parameter tuning.
    """
    def __init__(
        self,
        downloaded_files: List[Union[str, dict]],
        parent=None,
        skip_first: int = 0,
        skip_last: int = 0,
    ):
        super().__init__(parent)
        self.setWindowTitle("Manual Download Selection & Skip Parameter Tuning")
        self.resize(950, 750)
        self.downloaded_files = downloaded_files
        self.skip_first = skip_first
        self.skip_last = skip_last
        self.cards: List[ClickableImageCard] = []
        self.checkboxes: Dict[str, Any] = {}  # Backward compatibility shim for legacy tests

        # Resolve target download directory & skip input parameters from parent hierarchy
        self.download_dir = ""
        p = parent
        while p is not None:
            if self.skip_first == 0:
                if hasattr(p, "skip_first_input"):
                    with contextlib.suppress(Exception):
                        self.skip_first = int(getattr(p, "skip_first_input").text().strip())
                elif hasattr(p, "skip_first_spin"):
                    with contextlib.suppress(Exception):
                        self.skip_first = int(getattr(p, "skip_first_spin").value())

            if self.skip_last == 0:
                if hasattr(p, "skip_last_input"):
                    with contextlib.suppress(Exception):
                        self.skip_last = int(getattr(p, "skip_last_input").text().strip())
                elif hasattr(p, "skip_last_spin"):
                    with contextlib.suppress(Exception):
                        self.skip_last = int(getattr(p, "skip_last_spin").value())

            if hasattr(p, "download_dir_path"):
                try:
                    self.download_dir = getattr(p, "download_dir_path").text().strip()
                    if self.download_dir:
                        break
                except Exception:
                    pass
            if hasattr(p, "download_dir"):
                try:
                    self.download_dir = str(getattr(p, "download_dir")).strip()
                    if self.download_dir:
                        break
                except Exception:
                    pass
            p = p.parent() if hasattr(p, "parent") and callable(p.parent) else None

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Title Label
        title = QLabel("Click any image card to toggle between KEEP (Blue) and DISCARD (Red). Unselected images will be deleted.")
        title.setStyleSheet("font-size: 13px; font-weight: bold; margin-bottom: 4px;")
        layout.addWidget(title)

        # Banner explaining counter IDs & Skip First/Last tuning
        tip_box = QFrame()
        tip_box.setStyleSheet("QFrame { background-color: #1e222a; border: 1px solid #00f0ff; border-radius: 6px; padding: 6px; margin-bottom: 8px; }")
        tip_layout = QVBoxLayout(tip_box)
        tip_layout.setContentsMargins(8, 6, 8, 6)

        tip_title = QLabel("💡 Download Metadata & Skip First/Last Parameter Tuning Guide")
        tip_title.setStyleSheet("color: #00f0ff; font-weight: bold; font-size: 12px;")

        tip_text = QLabel(
            "Each card shows source Page URL, Page #, and Pos # on Page (counter ID). Click anywhere on a card to toggle state:\n"
            "• Blue Edge / Background = KEEP (Selected)\n"
            "• Red Edge / Background = DISCARD (Will be deleted on Confirm)\n"
            "Images within Skip First / Skip Last ranges are automatically pre-marked in RED as DISCARD!"
        )
        tip_text.setStyleSheet("color: #cccccc; font-size: 11px;")
        tip_text.setWordWrap(True)

        tip_layout.addWidget(tip_title)
        tip_layout.addWidget(tip_text)
        layout.addWidget(tip_box)

        # Scroll Area for images grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.grid_layout = QGridLayout(scroll_content)
        self.grid_layout.setSpacing(15)

        # Add images to grid
        cols = 4
        for idx, item in enumerate(self.downloaded_files):
            card = self.create_image_card(item, idx)
            self.cards.append(card)

            # Register in checkboxes dict for legacy compatibility shims/tests
            shim_chk = type("ShimChk", (), {"isChecked": lambda self_c, c=card: c.is_kept})()
            self.checkboxes[card.clean_path] = shim_chk
            self.checkboxes[card.raw_path] = shim_chk
            if isinstance(item, dict) and "path" in item:
                self.checkboxes[item["path"]] = shim_chk

            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Control Buttons (Select All / Deselect All)
        ctrl_layout = QHBoxLayout()
        btn_all = QPushButton("Keep All (Select All)")
        btn_all.clicked.connect(self.select_all)
        btn_none = QPushButton("Discard All (Deselect All)")
        btn_none.clicked.connect(self.deselect_all)
        ctrl_layout.addWidget(btn_all)
        ctrl_layout.addWidget(btn_none)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # Dialog Buttons (Confirm / Cancel)
        buttons_layout = QHBoxLayout()
        self.btn_confirm = QPushButton("Confirm (Keep Selected)")
        self.btn_confirm.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px;")
        self.btn_confirm.clicked.connect(self.accept)

        self.btn_cancel = QPushButton("Cancel (Discard All)")
        self.btn_cancel.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 10px;")
        self.btn_cancel.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_confirm)
        buttons_layout.addWidget(self.btn_cancel)
        layout.addLayout(buttons_layout)

    def create_image_card(self, item: Union[str, dict], idx: int) -> ClickableImageCard:
        if isinstance(item, str) and item.strip().startswith("{"):
            with contextlib.suppress(Exception):
                import json
                item = json.loads(item)

        raw_path = item.get("path", "") if isinstance(item, dict) else str(item)
        clean_path = raw_path.split("?")[0].split("#")[0]

        # 1. Resolve relative path or missing file via download_dir
        if not os.path.exists(clean_path):
            fname = os.path.basename(clean_path)
            if self.download_dir:
                candidate = os.path.join(self.download_dir, fname)
                if os.path.exists(candidate):
                    clean_path = candidate
                else:
                    for ext in (".jpeg", ".jpg", ".png", ".webp", ".gif", ".bmp"):
                        if os.path.exists(candidate + ext):
                            clean_path = candidate + ext
                            break

        # 2. Ultimate Fail-Safe: Match file by download index if file is still not found directly
        if not os.path.exists(clean_path) and self.download_dir and os.path.exists(self.download_dir):
            disk_files = sorted([
                os.path.join(self.download_dir, f)
                for f in os.listdir(self.download_dir)
                if any(f.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"))
            ])
            if 0 <= idx < len(disk_files):
                clean_path = disk_files[idx]

        card = ClickableImageCard(clean_path, raw_path, item, idx, self)

        # Pre-mark skipped images as DISCARD (Red border & background)
        index_on_page = idx + 1
        total_on_page = len(self.downloaded_files)
        item_skip_first = self.skip_first
        item_skip_last = self.skip_last

        if isinstance(item, dict):
            index_on_page = item.get("index_on_page", idx + 1)
            if item.get("total_on_page"):
                total_on_page = int(item["total_on_page"])
            if "skip_first" in item and item["skip_first"]:
                item_skip_first = int(item["skip_first"])
            if "skip_last" in item and item["skip_last"]:
                item_skip_last = int(item["skip_last"])

        if item_skip_first > 0 and index_on_page <= item_skip_first:
            card.set_kept(False)
        elif item_skip_last > 0 and total_on_page > 0 and index_on_page > (total_on_page - item_skip_last):
            card.set_kept(False)

        return card

    def select_all(self):
        for card in self.cards:
            card.set_kept(True)

    def deselect_all(self):
        for card in self.cards:
            card.set_kept(False)

    def get_kept_paths(self) -> List[str]:
        """Return absolute file paths of images marked as KEEP."""
        return [card.clean_path for card in self.cards if card.is_kept]

    def get_pruned_paths(self) -> List[str]:
        """Return absolute file paths of images marked as DISCARD."""
        return [card.clean_path for card in self.cards if not card.is_kept]


class DuplicateConfigDialog(QDialog):
    """
    Dialog to configure automated duplicate detection options.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Automated Selection: Duplicate Config")
        self.resize(600, 450)
        self.search_dirs: List[str] = []

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Title/Description
        desc = QLabel("Configure duplicate detection parameters to scan your downloads:")
        desc.setStyleSheet("font-size: 13px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(desc)

        # Method Options
        self.chk_exact = QCheckBox("Exact Content Match (SHA-256 Hash)")
        self.chk_exact.setChecked(True)
        layout.addWidget(self.chk_exact)

        self.chk_phash = QCheckBox("Approximate Match (Perceptual Hash - pHash)")
        self.chk_phash.setChecked(True)
        self.chk_phash.toggled.connect(self.on_phash_toggled)
        layout.addWidget(self.chk_phash)

        # Hamming Threshold selection
        thresh_layout = QHBoxLayout()
        self.lbl_thresh = QLabel("pHash Hamming Distance Threshold (1-64):")
        self.spin_thresh = QSpinBox()
        self.spin_thresh.setRange(1, 64)
        self.spin_thresh.setValue(10)
        self.spin_thresh.setToolTip("Lower is stricter (more identical), higher is looser. Default is 10.")
        thresh_layout.addWidget(self.lbl_thresh)
        thresh_layout.addWidget(self.spin_thresh)
        thresh_layout.addStretch()
        layout.addLayout(thresh_layout)

        # Reference Search Directories Group
        layout.addSpacing(10)
        layout.addWidget(QLabel("<b>Reference Directories to scan against (optional):</b>"))

        self.dir_list = QListWidget()
        layout.addWidget(self.dir_list)

        dir_buttons = QHBoxLayout()
        btn_add_dir = QPushButton("Add Folder...")
        btn_add_dir.clicked.connect(self.add_directory)
        btn_remove_dir = QPushButton("Remove Selected")
        btn_remove_dir.clicked.connect(self.remove_directory)
        dir_buttons.addWidget(btn_add_dir)
        dir_buttons.addWidget(btn_remove_dir)
        dir_buttons.addStretch()
        layout.addLayout(dir_buttons)

        # Internal duplicate check
        self.chk_internal = QCheckBox("Check for duplicates within the downloaded batch too")
        self.chk_internal.setChecked(True)
        layout.addWidget(self.chk_internal)

        layout.addSpacing(15)

        # Dialog Buttons
        buttons_layout = QHBoxLayout()
        btn_search = QPushButton("Run Duplicate Search")
        btn_search.setStyleSheet("background-color: #007AFF; color: white; font-weight: bold; padding: 8px 15px;")
        btn_search.clicked.connect(self.accept)

        btn_cancel = QPushButton("Cancel (Discard Downloads)")
        btn_cancel.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 8px 15px;")
        btn_cancel.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(btn_search)
        buttons_layout.addWidget(btn_cancel)
        layout.addLayout(buttons_layout)

    def on_phash_toggled(self, checked: bool):
        self.lbl_thresh.setEnabled(checked)
        self.spin_thresh.setEnabled(checked)

    def add_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Reference Directory")
        if dir_path and dir_path not in self.search_dirs:
            self.search_dirs.append(dir_path)
            self.dir_list.addItem(dir_path)

    def remove_directory(self):
        row = self.dir_list.currentRow()
        if row >= 0:
            item = self.dir_list.takeItem(row)
            if item.text() in self.search_dirs:
                self.search_dirs.remove(item.text())

    def get_config(self) -> Dict[str, Any]:
        return {
            "exact_hash": self.chk_exact.isChecked(),
            "phash": self.chk_phash.isChecked(),
            "threshold": self.spin_thresh.value(),
            "search_dirs": self.search_dirs,
            "check_internal": self.chk_internal.isChecked()
        }


class DeduplicationPruningDialog(QDialog):
    """
    Shows downloaded images paired with any exact/approximate duplicates found.
    Allows Confirm (auto prune duplicates), Edit (manual check), and Cancel (discard).
    """
    def __init__(self, downloaded_files: List[str], duplicates_map: Dict[str, List[str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Automated Selection: Prune Duplicates")
        self.resize(950, 700)
        self.downloaded_files = downloaded_files
        self.duplicates_map = duplicates_map
        self.checkboxes: Dict[str, QCheckBox] = {}

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Title / Summary info
        num_with_dupes = sum(1 for p in self.downloaded_files if self.duplicates_map.get(p))
        summary = QLabel(
            f"Duplicate search complete! Found **{num_with_dupes}** image(s) with duplicates out of "
            f"**{len(self.downloaded_files)}** downloaded image(s).\n"
            f"Images with duplicates are unchecked by default (will be deleted)."
        )
        summary.setStyleSheet("font-size: 13px; font-weight: bold; color: #00bcd4; margin-bottom: 10px;")
        layout.addWidget(summary)

        # Scroll Area for image items list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)

        for path in self.downloaded_files:
            item_widget = self.create_pruning_row(path)
            scroll_layout.addWidget(item_widget)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Buttons
        buttons_layout = QHBoxLayout()
        btn_confirm = QPushButton("Confirm (Apply Pruning)")
        btn_confirm.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px 20px;")
        btn_confirm.clicked.connect(self.accept)

        btn_cancel = QPushButton("Cancel (Discard All Downloads)")
        btn_cancel.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 10px 20px;")
        btn_cancel.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(btn_confirm)
        buttons_layout.addWidget(btn_cancel)
        layout.addLayout(buttons_layout)

    def create_pruning_row(self, path: str) -> QFrame:
        row = QFrame()
        row.setFrameShape(QFrame.Shape.StyledPanel)

        dupes = self.duplicates_map.get(path, [])
        has_dupes = len(dupes) > 0

        if has_dupes:
            row.setStyleSheet("QFrame { border: 1px solid #c0392b; border-radius: 8px; background-color: #2c1a1a; padding: 8px; }")
        else:
            row.setStyleSheet("QFrame { border: 1px solid #27ae60; border-radius: 8px; background-color: #1a2c1a; padding: 8px; }")

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 5, 10, 5)

        # 1. Thumbnail
        thumb_label = QLabel()
        thumb_label.setFixedSize(100, 100)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            thumb_label.setPixmap(pixmap.scaled(90, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            thumb_label.setText("No Preview")
            thumb_label.setStyleSheet("color: #888888; font-style: italic;")
        row_layout.addWidget(thumb_label)

        # 2. Details
        details_layout = QVBoxLayout()
        filename = os.path.basename(path)
        name_lbl = QLabel(f"<b>{filename}</b> ({get_file_size_str(path)})")
        name_lbl.setStyleSheet("color: white; font-size: 12px;")
        path_lbl = QLabel(path)
        path_lbl.setStyleSheet("color: #888888; font-size: 10px;")

        details_layout.addWidget(name_lbl)
        details_layout.addWidget(path_lbl)

        # Duplicates details
        if has_dupes:
            dup_title = QLabel(f"⚠️ **Duplicate(s) Found ({len(dupes)}):**")
            dup_title.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 11px;")
            details_layout.addWidget(dup_title)
            for dup_path in dupes:
                dup_lbl = QLabel(f"• {dup_path} ({get_file_size_str(dup_path)})")
                dup_lbl.setStyleSheet("color: #ffaa99; font-size: 10px;")
                dup_lbl.setWordWrap(True)
                details_layout.addWidget(dup_lbl)
        else:
            ok_lbl = QLabel("✅ No duplicates detected.")
            ok_lbl.setStyleSheet("color: #2ecc71; font-size: 11px;")
            details_layout.addWidget(ok_lbl)

        row_layout.addLayout(details_layout, 1)

        # 3. Checkbox "Keep"
        chk = QCheckBox("Keep")
        chk.setChecked(not has_dupes)  # Default: keep only if NO duplicates found
        self.checkboxes[path] = chk
        row_layout.addWidget(chk, 0, Qt.AlignmentFlag.AlignVCenter)

        return row


# Main runner helper to execute the duplicate scan with a QProgressDialog
def run_duplicate_scan(  # noqa: C901
    downloaded_files: List[str],
    config: Dict[str, Any],
    parent_widget=None
) -> Dict[str, List[str]]:
    """
    Computes exact and approximate matches for the downloaded files.
    Returns a mapping of downloaded_file_path -> list of duplicate paths.
    """
    exact_hash = config.get("exact_hash", True)
    phash = config.get("phash", True)
    threshold = config.get("threshold", 10)
    search_dirs = config.get("search_dirs", [])
    check_internal = config.get("check_internal", True)

    results: Dict[str, List[str]] = {p: [] for p in downloaded_files}

    # 1. Find reference files
    ref_files: List[str] = []
    image_exts = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

    # We can pre-scan search directories
    for sdir in search_dirs:
        if os.path.exists(sdir) and os.path.isdir(sdir):
            for root, _, files in os.walk(sdir):
                for f in files:
                    if f.lower().endswith(image_exts):
                        ref_files.append(os.path.join(root, f))

    # Initialize progress dialog
    total_steps = 0
    if exact_hash:
        total_steps += len(downloaded_files)
    if phash:
        total_steps += len(downloaded_files) + len(ref_files)

    progress = QProgressDialog("Scanning directories and comparing hashes...", "Cancel", 0, max(total_steps, 1), parent_widget)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setValue(0)

    current_step = 0

    # Cache calculated hashes to avoid re-calculation
    downloaded_exact_hashes: Dict[str, str] = {}
    downloaded_phashes: Dict[str, int] = {}

    # Size-based indexing for exact match reference files to optimize scanning
    size_to_ref_files: Dict[int, List[str]] = {}
    if exact_hash:
        downloaded_sizes = {os.path.getsize(p) for p in downloaded_files if os.path.exists(p)}
        for ref_p in ref_files:
            try:
                sz = os.path.getsize(ref_p)
                if sz in downloaded_sizes:
                    if sz not in size_to_ref_files:
                        size_to_ref_files[sz] = []
                    size_to_ref_files[sz].append(ref_p)
            except OSError:
                continue

    # --- EXACT HASH COMPARE ---
    if exact_hash:
        # Calculate downloaded file hashes
        for p in downloaded_files:
            if progress.wasCanceled():
                return results
            if os.path.exists(p):
                h = get_file_sha256(p)
                if h:
                    downloaded_exact_hashes[p] = h
            current_step += 1
            progress.setValue(current_step)

        # Compare with reference files (size matches)
        for p_down, h_down in downloaded_exact_hashes.items():
            if progress.wasCanceled():
                return results
            try:
                sz = os.path.getsize(p_down)
                matching_refs = size_to_ref_files.get(sz, [])
                for p_ref in matching_refs:
                    # Ignore comparing with itself
                    if os.path.abspath(p_ref) == os.path.abspath(p_down):
                        continue
                    h_ref = get_file_sha256(p_ref)
                    if h_ref == h_down and p_ref not in results[p_down]:
                        results[p_down].append(p_ref)
            except OSError:
                continue

        # Check internally
        if check_internal:
            for p1 in downloaded_files:
                for p2 in downloaded_files:
                    if (
                        p1 != p2
                        and p1 in downloaded_exact_hashes
                        and p2 in downloaded_exact_hashes
                        and downloaded_exact_hashes[p1] == downloaded_exact_hashes[p2]
                        and p2 not in results[p1]
                    ):
                        results[p1].append(p2)

    # --- PHASH COMPARE ---
    if phash:
        # Compute phash of downloaded files
        for p in downloaded_files:
            if progress.wasCanceled():
                return results
            if os.path.exists(p):
                ph = compute_phash_file(p)
                if ph is not None:
                    downloaded_phashes[p] = ph
            current_step += 1
            progress.setValue(current_step)

        # Compute phash of reference files
        ref_phashes: List[Tuple[str, int]] = []
        for p in ref_files:
            if progress.wasCanceled():
                return results
            if os.path.exists(p):
                ph = compute_phash_file(p)
                if ph is not None:
                    ref_phashes.append((p, ph))
            current_step += 1
            progress.setValue(current_step)

        # Compare phashes
        for p_down, ph_down in downloaded_phashes.items():
            if progress.wasCanceled():
                return results
            # Reference matches
            for p_ref, ph_ref in ref_phashes:
                if os.path.abspath(p_ref) == os.path.abspath(p_down):
                    continue
                dist = _hamming64(ph_down, ph_ref)
                if dist <= threshold and p_ref not in results[p_down]:
                    results[p_down].append(p_ref)

            # Internal matches
            if check_internal:
                for p_other, ph_other in downloaded_phashes.items():
                    if p_down != p_other:
                        dist = _hamming64(ph_down, ph_other)
                        if dist <= threshold and p_other not in results[p_down]:
                            results[p_down].append(p_other)

    progress.close()
    return results
