"""Manual download selection dialog + image cards (crawler review UI).

Split from ``crawler_selection_dialogs`` (§5.17 Option B, #629) — pure
code motion, no logic change.
"""

import contextlib
import hashlib
import logging
import os
from typing import Any, Dict, List, Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.src.theming.theme_api import color, qss

logger = logging.getLogger(__name__)

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
            thumb_label.setStyleSheet(qss("muted_label"))

        # Metadata
        filename = os.path.basename(clean_path)
        if len(filename) > 20:
            filename = filename[:17] + "..."

        size_str = get_file_size_str(clean_path)
        meta_html = f"<b>{filename}</b> ({size_str})<br/>"
        meta_html += f"<span style='color: {color('accent')};'><b>Pos on Page: #{index_on_page}</b></span> &nbsp;|&nbsp; Page #{page_num}<br/>"
        meta_html += f"<span style='color: {color('muted_text')};'>Global ID: #{global_id}</span>"

        if page_url:
            short_url = page_url.replace("https://", "").replace("http://", "")
            if len(short_url) > 26:
                short_url = short_url[:23] + "..."
            meta_html += f"<br/><span style='color: {color('muted_text')};'>URL: {short_url}</span>"

        info_label = QLabel(meta_html)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setStyleSheet(qss("task_close_status"))
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
            # KEEP State: accent border on dark surface
            self.setStyleSheet(qss("crawler_card_keep"))
            self.status_badge.setText("✓ KEEP (Selected)")
            self.status_badge.setStyleSheet(qss("crawler_badge_keep"))
        else:
            # NOT KEEP State: danger border on dark surface
            self.setStyleSheet(qss("crawler_card_discard"))
            self.status_badge.setText("✗ DISCARD (Will Delete)")
            self.status_badge.setStyleSheet(qss("crawler_badge_discard"))


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
                        self.skip_first = int(p.skip_first_input.text().strip())
                elif hasattr(p, "skip_first_spin"):
                    with contextlib.suppress(Exception):
                        self.skip_first = int(p.skip_first_spin.value())

            if self.skip_last == 0:
                if hasattr(p, "skip_last_input"):
                    with contextlib.suppress(Exception):
                        self.skip_last = int(p.skip_last_input.text().strip())
                elif hasattr(p, "skip_last_spin"):
                    with contextlib.suppress(Exception):
                        self.skip_last = int(p.skip_last_spin.value())

            if hasattr(p, "download_dir_path"):
                try:
                    self.download_dir = p.download_dir_path.text().strip()
                    if self.download_dir:
                        break
                except Exception:
                    logger.debug("Suppressed Exception in ManualSelectionDialog.__init__", exc_info=True)
            if hasattr(p, "download_dir"):
                try:
                    self.download_dir = str(p.download_dir).strip()
                    if self.download_dir:
                        break
                except Exception:
                    logger.debug("Suppressed Exception in ManualSelectionDialog.__init__", exc_info=True)
            p = p.parent() if hasattr(p, "parent") and callable(p.parent) else None

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Title Label
        title = QLabel("Click any image card to toggle between KEEP (Blue) and DISCARD (Red). Unselected images will be deleted.")
        title.setStyleSheet(qss("task_close_header"))
        layout.addWidget(title)

        # Banner explaining counter IDs & Skip First/Last tuning
        tip_box = QFrame()
        tip_box.setStyleSheet(qss("crawler_tip_box"))
        tip_layout = QVBoxLayout(tip_box)
        tip_layout.setContentsMargins(8, 6, 8, 6)

        tip_title = QLabel("💡 Download Metadata & Skip First/Last Parameter Tuning Guide")
        tip_title.setStyleSheet(qss("asp_dialog_title"))

        tip_text = QLabel(
            "Each card shows source Page URL, Page #, and Pos # on Page (counter ID). Click anywhere on a card to toggle state:\n"
            "• Blue Edge / Background = KEEP (Selected)\n"
            "• Red Edge / Background = DISCARD (Will be deleted on Confirm)\n"
            "Images within Skip First / Skip Last ranges are automatically pre-marked in RED as DISCARD!"
        )
        tip_text.setStyleSheet(qss("queue_filename"))
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
        self.btn_confirm.setStyleSheet(qss("dialog_btn_success"))
        self.btn_confirm.clicked.connect(self.accept)

        self.btn_cancel = QPushButton("Cancel (Discard All)")
        self.btn_cancel.setStyleSheet(qss("dialog_btn_danger"))
        self.btn_cancel.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_confirm)
        buttons_layout.addWidget(self.btn_cancel)
        layout.addLayout(buttons_layout)

    def create_image_card(self, item: Union[str, dict], idx: int) -> ClickableImageCard:
        # Signal(object) emits dicts directly now; plain strings are a legacy fallback
        if isinstance(item, str) and item.strip().startswith("{"):
            with contextlib.suppress(Exception):
                import json
                item = json.loads(item)

        raw_path = item.get("path", "") if isinstance(item, dict) else str(item)
        clean_path = os.path.normpath(raw_path.split("?")[0].split("#")[0])

        # 1. Resolve relative path or missing file via download_dir
        if not os.path.isfile(clean_path):
            fname = os.path.basename(clean_path)
            if self.download_dir:
                candidate = os.path.join(self.download_dir, fname)
                if os.path.isfile(candidate):
                    clean_path = candidate
                else:
                    for ext in (".jpeg", ".jpg", ".png", ".webp", ".gif", ".bmp"):
                        if os.path.isfile(candidate + ext):
                            clean_path = candidate + ext
                            break

        # 2. Fail-Safe: Match file by global_id then fallback to sorted-disk index
        if not os.path.isfile(clean_path) and self.download_dir and os.path.isdir(self.download_dir):
            disk_files = sorted([
                os.path.join(self.download_dir, f)
                for f in os.listdir(self.download_dir)
                if any(f.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"))
            ])
            # Try matching by global_id first (1-based)
            global_id = item.get("global_id", 0) if isinstance(item, dict) else 0
            if global_id > 0 and global_id <= len(disk_files):
                clean_path = disk_files[global_id - 1]
            elif 0 <= idx < len(disk_files):
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

        if item_skip_first > 0 and index_on_page <= item_skip_first or item_skip_last > 0 and total_on_page > 0 and index_on_page > (total_on_page - item_skip_last):
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


__all__ = [
    "ClickableImageCard",
    "ManualSelectionDialog",
    "_hamming64",
    "get_file_sha256",
    "get_file_size_str",
]
