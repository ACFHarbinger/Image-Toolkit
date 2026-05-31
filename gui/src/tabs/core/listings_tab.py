import json
import uuid
import subprocess
import tempfile
import cv2
from pathlib import Path
from datetime import date
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, Signal, Slot, QUrl, QSize, QThread, QTimer, QObject
from PySide6.QtGui import QPixmap, QDesktopServices, QImage, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QSpinBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFrame,
    QGroupBox,
    QFormLayout,
    QSplitter,
    QDialog,
    QDateEdit,
    QScrollArea,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)

import os
import backend.src.constants as udef
from backend.src.constants import IMAGE_TOOLKIT_DIR
from backend.src.core.vault_manager import VaultManager  # noqa: F401
from ...styles.style import apply_shadow_effect, SHARED_BUTTON_STYLE
from ...components import DoubleClickableLabel
from ...constants.listings import (
    LISTINGS_FILE,
    ENTITIES_FILE,
    LISTING_IMAGES_DIR,
    ENTRY_TYPES,
    ENTRY_STATUS,
    TYPE_COLORS,
    STATUS_COLORS,
    ENTITY_TYPES,
    ENTITY_ROLES,
    ENTITY_TYPE_COLORS,
    ENTITY_ROLE_COLORS,
    CARD_SIZE,
    THUMB_SIZE,
    PLACEHOLDER,
    ENTITY_PLACEHOLDER,
    VIDEO_IMPORT_EXTS,
)


def open_file_location(path: str):
    if not path:
        return
    import subprocess
    import platform

    p = Path(path)
    if not p.exists():
        return

    # Try showing item in file manager
    if platform.system() == "Linux":
        try:
            subprocess.run(
                [
                    "dbus-send",
                    "--session",
                    "--print-reply",
                    "--dest=org.freedesktop.FileManager1",
                    "/org/freedesktop/FileManager1",
                    "org.freedesktop.FileManager1.ShowItems",
                    f"array:string:file://{p.absolute()}",
                    "string:",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))
    elif platform.system() == "Windows":
        subprocess.run(f'explorer.exe /select,"{p.absolute()}"')
    elif platform.system() == "Darwin":
        subprocess.run(["open", "-R", str(p.absolute())])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))


def open_web_link(url_str: str):
    if not url_str:
        return
    if not url_str.startswith(("http://", "https://")):
        url_str = "https://" + url_str
    QDesktopServices.openUrl(QUrl(url_str))


def extract_video_frame_via_ffmpeg(
    video_path: str, frame_idx: int, total_frames: int, fps: float
):
    if not fps or fps <= 0:
        fps = 24.0
    seconds = frame_idx / fps

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_name = tmp.name

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{seconds:.3f}",
            "-i",
            video_path,
            "-vframes",
            "1",
            "-update",
            "1",
            tmp_name,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and Path(tmp_name).exists():
            img = cv2.imread(tmp_name)
            if img is not None:
                return img
    except Exception as e:
        print(f"ffmpeg fallback failed: {e}")
    finally:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except Exception:
            pass
    return None


def generate_thumbnail_from_file(file_path: str, dest_path: str) -> bool:
    import cv2
    import shutil
    from pathlib import Path

    p = Path(file_path)
    if not p.exists():
        return False

    suffix = p.suffix.lower()

    # 1. Image formats
    if suffix in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
        try:
            shutil.copy2(file_path, dest_path)
            return True
        except Exception as e:
            print(f"Failed to copy image for thumbnail: {e}")
            return False

    # 2. PDF format
    elif suffix == ".pdf":
        try:
            from PySide6.QtPdf import QPdfDocument
            from PySide6.QtCore import QSize

            doc = QPdfDocument()
            if doc.load(str(p.absolute())) == QPdfDocument.Status.Ready:
                qimg = doc.render(0, QSize(600, 800))
                if not qimg.isNull():
                    return qimg.save(dest_path)
        except Exception as e:
            print(f"Failed to render PDF thumbnail: {e}")
            return False

    # 3. Video formats
    elif suffix in (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v"):
        try:
            # First, probe metadata cleanly using OpenCV (doesn't trigger decoding)
            try:
                cap = cv2.VideoCapture(
                    str(p.absolute()),
                    cv2.CAP_FFMPEG,
                    [cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_NONE],
                )
            except Exception:
                cap = cv2.VideoCapture(str(p.absolute()))

            total_frames = 0
            fps = 24.0
            if cap.isOpened():
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                cap.release()

            if total_frames <= 0:
                total_frames = 1000

            target_frame = min(max(1, total_frames // 10), total_frames - 1)

            # Try ultra-robust software ffmpeg extraction first
            frame = extract_video_frame_via_ffmpeg(
                str(p.absolute()), target_frame, total_frames, fps
            )
            if frame is None:
                # Try frame 0 as fallback
                frame = extract_video_frame_via_ffmpeg(
                    str(p.absolute()), 0, total_frames, fps
                )

            if frame is not None:
                cv2.imwrite(dest_path, frame)
                return True

            # If ffmpeg wasn't available or failed, try direct OpenCV decoding
            try:
                cap = cv2.VideoCapture(str(p.absolute()))
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    success, frame = cap.read()
                    if success:
                        cv2.imwrite(dest_path, frame)
                        cap.release()
                        return True
                    cap.release()
            except Exception:
                pass
        except Exception as e:
            print(f"Failed to extract video thumbnail: {e}")
            return False

    return False


# -------------------------------------------------------------------
# Async frame extraction worker (used by ThumbnailSelectionDialog)
# -------------------------------------------------------------------
class _FrameWorkerSignals(QObject):
    frame_ready = Signal(object)  # emits a numpy ndarray (BGR)
    failed = Signal()


class _FrameWorker(QThread):
    """Extracts a single video frame off the main thread via ffmpeg subprocess.

    Cancellable: if a new request arrives before the previous finishes, the
    caller sets `_cancelled = True` and the worker discards its result.
    """

    def __init__(self, video_path: str, frame_idx: int, total_frames: int, fps: float):
        super().__init__()
        self.video_path = video_path
        self.frame_idx = frame_idx
        self.total_frames = total_frames
        self.fps = fps
        self.signals = _FrameWorkerSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        frame = extract_video_frame_via_ffmpeg(
            self.video_path, self.frame_idx, self.total_frames, self.fps
        )
        if self._cancelled:
            return
        if frame is not None:
            self.signals.frame_ready.emit(frame)
        else:
            self.signals.failed.emit()


def _parse_video_series(filename: str):
    """
    Parse '<Series Name> - <EP_NUM> <suffix>.<ext>' into (series_name, ep_num_or_None).
    Falls back to (stem, None) for filenames that don't contain ' - '.
    """
    import re as _re
    stem = Path(filename).stem
    parts = stem.split(" - ", 1)
    if len(parts) < 2:
        return stem.strip(), None
    series_name = parts[0].strip()
    ep_part = parts[1].strip()
    m = _re.match(r"^(\d+)", ep_part)
    return series_name, (int(m.group(1)) if m else None)


def _scan_video_directory(directory: str) -> "dict[str, list[tuple]]":
    """Scan *directory* (max-depth 1) for video files.

    Returns ``{series_name: [(ep_num_or_None, abs_path), ...]}`` with each
    series' list sorted by episode number (None episodes go last).
    """
    result: dict = {}
    dir_path = Path(directory)
    try:
        entries = sorted(dir_path.iterdir(), key=lambda e: e.name.lower())
    except OSError:
        return result
    for entry in entries:
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in VIDEO_IMPORT_EXTS:
            continue
        series_name, ep_num = _parse_video_series(entry.name)
        result.setdefault(series_name, []).append((ep_num, str(entry.absolute())))
    for name in result:
        result[name].sort(key=lambda x: (x[0] is None, x[0] or 0))
    return result


# -------------------------------------------------------------------
# Helper – coloured badge label
# -------------------------------------------------------------------
def _badge(text: str, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"background:{color}; color:white; font-size:9px; font-weight:bold;"
        f"border-radius:4px; padding:1px 5px;"
    )
    return lbl


# -------------------------------------------------------------------
# Episode Dialog (Content Listings)
# -------------------------------------------------------------------
class EpisodeDialog(QDialog):
    def __init__(self, episode_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Episode / Chapter Details")
        self.setMinimumWidth(400)
        self.setStyleSheet("background:#2c2f33; color:white;")

        self.data = episode_data or {}
        self.image_path = self.data.get("image_path", "")

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.f_number = QSpinBox()
        self.f_number.setRange(1, 999999)
        self.f_number.setValue(self.data.get("number", 1))

        self.f_title = QLineEdit()
        self.f_title.setPlaceholderText("Episode Title (optional)")
        self.f_title.setText(self.data.get("title", ""))

        self.f_date = QDateEdit()
        self.f_date.setCalendarPopup(True)
        # Handle date parsing/setting
        d_str = self.data.get("date_watched")
        if d_str:
            self.f_date.setDate(date.fromisoformat(d_str))
        else:
            self.f_date.setDate(date.today())

        self.f_rating = QSpinBox()
        self.f_rating.setRange(0, 10)
        self.f_rating.setSpecialValueText("No rating")
        self.f_rating.setValue(self.data.get("rating", 0))

        self.f_review = QTextEdit()
        self.f_review.setPlaceholderText("Episode notes / review…")
        self.f_review.setPlainText(self.data.get("review", ""))
        self.f_review.setFixedHeight(80)

        self.f_local_file = QLineEdit()
        self.f_local_file.setPlaceholderText("Local File path (optional)")
        self.f_local_file.setText(self.data.get("local_file", ""))

        local_file_btn = QPushButton("📁 Browse")
        local_file_btn.setStyleSheet(
            "background-color:#4f545c; padding: 4px 8px; color: white;"
        )
        local_file_btn.clicked.connect(self._browse_local_file)

        file_layout = QHBoxLayout()
        file_layout.addWidget(self.f_local_file)
        file_layout.addWidget(local_file_btn)

        self.f_web_link = QLineEdit()
        self.f_web_link.setPlaceholderText("https://... (optional)")
        self.f_web_link.setText(self.data.get("web_link", ""))

        form.addRow("Number", self.f_number)
        form.addRow("Title", self.f_title)
        form.addRow("Date", self.f_date)
        form.addRow("Rating", self.f_rating)
        form.addRow("Review", self.f_review)
        form.addRow("Local File", file_layout)
        form.addRow("Web Link", self.f_web_link)
        layout.addLayout(form)

        # Image picker
        img_layout = QHBoxLayout()
        self.img_preview = DoubleClickableLabel()
        self.img_preview.setFixedSize(120, 120)
        self.img_preview.setAlignment(Qt.AlignCenter)
        self.img_preview.setStyleSheet("border:1px dashed #4f545c; border-radius:4px;")
        self._update_preview()
        img_layout.addWidget(self.img_preview)

        btn_v_layout = QVBoxLayout()
        browse_btn = QPushButton("📁 Browse Image")
        browse_btn.clicked.connect(self._browse)

        gen_btn = QPushButton("⚡ Gen Thumbnail")
        gen_btn.setStyleSheet(
            "background-color:#e67e22; color:white; font-weight:bold; padding: 4px 8px; border-radius: 4px;"
        )
        gen_btn.clicked.connect(self._generate_thumbnail)

        btn_v_layout.addWidget(browse_btn)
        btn_v_layout.addWidget(gen_btn)
        btn_v_layout.addStretch()
        img_layout.addLayout(btn_v_layout)
        layout.addLayout(img_layout)

        # Buttons
        btns = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Episode Image", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self.image_path = path
            self._update_preview()

    def _browse_local_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Local Episode File",
            "",
            "All Files (*.*);;Videos (*.mp4 *.mkv *.avi *.mov *.webm);;Documents (*.pdf *.epub)",
        )
        if path:
            self.f_local_file.setText(path)

    def _update_preview(self):
        self.img_preview.set_image_path(self.image_path)
        if self.image_path and Path(self.image_path).exists():
            px = QPixmap(self.image_path).scaled(
                120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.img_preview.setPixmap(px)
        else:
            self.img_preview.setText("No Image")

    def _generate_thumbnail(self):
        file_path = self.f_local_file.text().strip()
        if not file_path:
            QMessageBox.warning(
                self,
                "No Local File",
                "Please specify a valid Local File first to generate a thumbnail.",
            )
            return

        p = Path(file_path)
        if not p.exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The local file at '{file_path}' does not exist.",
            )
            return

        suffix = p.suffix.lower()
        LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        ep_id = self.data.get("id") or str(uuid.uuid4())
        dest_p = LISTING_IMAGES_DIR / f"ep_{ep_id}.png"

        # Image formats - shortcut direct copy
        if suffix in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
            import shutil

            try:
                shutil.copy2(file_path, dest_p)
                self.image_path = str(dest_p.absolute())
                self._update_preview()
                QMessageBox.information(
                    self, "Success", "Image set as thumbnail successfully!"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to set image: {e}")
            return

        # Video / PDF formats - selection dialog
        if suffix in (".pdf", ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v"):
            dlg = ThumbnailSelectionDialog(file_path, parent=self)
            if dlg.exec() == QDialog.Accepted and dlg.selected_image:
                if dlg.selected_image.save(str(dest_p.absolute())):
                    self.image_path = str(dest_p.absolute())
                    self._update_preview()
                    QMessageBox.information(
                        self,
                        "Success",
                        "Successfully saved selected representative thumbnail!",
                    )
                else:
                    QMessageBox.critical(
                        self, "Error", "Failed to save selected thumbnail image."
                    )
            return

        QMessageBox.warning(
            self,
            "Unsupported Format",
            "This file format is not supported for generating a thumbnail.",
        )

    def get_data(self) -> Dict[str, Any]:
        # QDate.toPython() returns datetime.date
        date_obj = self.f_date.date().toPython()
        return {
            "id": self.data.get("id") or str(uuid.uuid4()),
            "number": self.f_number.value(),
            "title": self.f_title.text().strip(),
            "date_watched": date_obj.isoformat(),
            "rating": self.f_rating.value(),
            "review": self.f_review.toPlainText().strip(),
            "image_path": self.image_path,
            "local_file": self.f_local_file.text().strip(),
            "web_link": self.f_web_link.text().strip(),
        }


# -------------------------------------------------------------------
# Credit / Work Dialog (Entity Listings)
# -------------------------------------------------------------------
class CreditDialog(QDialog):
    def __init__(self, credit_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Credit / Work Details")
        self.setMinimumWidth(400)
        self.setStyleSheet("background:#2c2f33; color:white;")

        self.data = credit_data or {}
        self.image_path = self.data.get("image_path", "")

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.f_title = QLineEdit()
        self.f_title.setPlaceholderText("Work / Show Title (e.g. Cowboy Bebop)")
        self.f_title.setText(self.data.get("title", ""))

        self.f_role = QLineEdit()
        self.f_role.setPlaceholderText(
            "Role / Character (e.g. Spike Spiegel / Director)"
        )
        self.f_role.setText(self.data.get("role", ""))

        self.f_year = QSpinBox()
        self.f_year.setRange(0, 2100)
        self.f_year.setValue(self.data.get("year", date.today().year))
        self.f_year.setSpecialValueText("Unknown")

        self.f_rating = QSpinBox()
        self.f_rating.setRange(0, 10)
        self.f_rating.setSpecialValueText("No rating")
        self.f_rating.setValue(self.data.get("rating", 0))

        self.f_notes = QTextEdit()
        self.f_notes.setPlaceholderText("Notes about this appearance / credit…")
        self.f_notes.setPlainText(self.data.get("notes", ""))
        self.f_notes.setFixedHeight(80)

        form.addRow("Work Title *", self.f_title)
        form.addRow("Role / Character", self.f_role)
        form.addRow("Year", self.f_year)
        form.addRow("Rating", self.f_rating)
        form.addRow("Notes", self.f_notes)
        layout.addLayout(form)

        # Image picker
        img_layout = QHBoxLayout()
        self.img_preview = DoubleClickableLabel()
        self.img_preview.setFixedSize(120, 120)
        self.img_preview.setAlignment(Qt.AlignCenter)
        self.img_preview.setStyleSheet("border:1px dashed #4f545c; border-radius:4px;")
        self._update_preview()
        img_layout.addWidget(self.img_preview)

        browse_btn = QPushButton("📁 Browse Image")
        browse_btn.clicked.connect(self._browse)
        img_layout.addWidget(browse_btn, alignment=Qt.AlignTop)
        layout.addLayout(img_layout)

        # Buttons
        btns = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Work Image", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self.image_path = path
            self._update_preview()

    def _update_preview(self):
        self.img_preview.set_image_path(self.image_path)
        if self.image_path and Path(self.image_path).exists():
            px = QPixmap(self.image_path).scaled(
                120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.img_preview.setPixmap(px)
        else:
            self.img_preview.setText("No Image")

    def get_data(self) -> Dict[str, Any]:
        return {
            "id": self.data.get("id") or str(uuid.uuid4()),
            "title": self.f_title.text().strip(),
            "role": self.f_role.text().strip(),
            "year": self.f_year.value(),
            "rating": self.f_rating.value(),
            "notes": self.f_notes.toPlainText().strip(),
            "image_path": self.image_path,
        }


# -------------------------------------------------------------------
# Associated Entities Dialog
# -------------------------------------------------------------------
class AssociatedEntitiesDialog(QDialog):
    def __init__(
        self, all_entities: List[Dict[str, Any]], selected_ids: List[str], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Select Associated Entities")
        self.setMinimumSize(400, 450)
        self.setStyleSheet("background:#2c2f33; color:white;")

        self.all_entities = all_entities
        self.selected_ids = set(selected_ids)

        layout = QVBoxLayout(self)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search entities by name or role…")
        self.search_box.textChanged.connect(self._filter_list)
        layout.addWidget(self.search_box)

        # List widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { background:#23272a; border:1px solid #4f545c; border-radius:6px; padding:4px; }"
            "QListWidget::item { color:white; padding:4px; border-bottom:1px solid #2c2f33; }"
            "QListWidget::item:hover { background:#00bcd4; color:black; }"
        )
        layout.addWidget(self.list_widget)

        self._populate_list()

        # Buttons
        btns = QHBoxLayout()
        ok_btn = QPushButton("Select")
        ok_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(ok_btn)
        layout.addLayout(btns)

    def _populate_list(self):
        self.list_widget.clear()
        query = self.search_box.text().lower()

        for ent in self.all_entities:
            name = ent.get("name", "Unnamed")
            role = ent.get("role", "Other")
            ent_type = ent.get("type", "Other")

            if query and query not in name.lower() and query not in role.lower():
                continue

            item = QListWidgetItem(f"{name} ({ent_type} - {role})")
            item.setData(Qt.UserRole, ent["id"])

            # Checkbox state
            if ent["id"] in self.selected_ids:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

            self.list_widget.addItem(item)

    def _filter_list(self):
        # We need to save the check state of currently visible items before repopulating
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            ent_id = item.data(Qt.UserRole)
            if item.checkState() == Qt.Checked:
                self.selected_ids.add(ent_id)
            else:
                self.selected_ids.discard(ent_id)

        self._populate_list()

    def get_selected_ids(self) -> List[str]:
        # Sync the final visible state
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            ent_id = item.data(Qt.UserRole)
            if item.checkState() == Qt.Checked:
                self.selected_ids.add(ent_id)
            else:
                self.selected_ids.discard(ent_id)
        return list(self.selected_ids)


# -------------------------------------------------------------------
# Card widget (Content Listings)
# -------------------------------------------------------------------
class _ListingCard(QWidget):
    clicked = Signal(str)  # entry id
    delete_requested = Signal(str)  # entry id
    add_requested = Signal()
    image_remove_requested = Signal(str)  # entry id

    def __init__(self, entry: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.entry = entry
        self._id = entry["id"]
        self.setFixedSize(CARD_SIZE + 10, CARD_SIZE + 50)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("listing_card")
        self.setStyleSheet(
            "QWidget#listing_card{background:#2c2f33;border:2px solid #4f545c;"
            "border-radius:8px;}"
            "QWidget#listing_card:hover{border:2px solid #00bcd4;}"
        )
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail
        self.thumb_label = DoubleClickableLabel()
        self.thumb_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("border:none;")
        self._apply_thumbnail(entry.get("image_path", ""))
        layout.addWidget(self.thumb_label, alignment=Qt.AlignHCenter)

        # Title
        title_lbl = QLabel(entry.get("title", "Untitled"))
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setWordWrap(False)
        title_lbl.setStyleSheet(
            "color:#ffffff;font-weight:bold;font-size:11px;border:none;"
        )
        title_lbl.setFixedWidth(CARD_SIZE - 4)
        fm = title_lbl.fontMetrics()
        title_lbl.setText(
            fm.elidedText(entry.get("title", "Untitled"), Qt.ElideRight, CARD_SIZE - 10)
        )
        title_lbl.setToolTip(entry.get("title", ""))
        layout.addWidget(title_lbl, alignment=Qt.AlignHCenter)

        # Badges row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(4)
        t = entry.get("type", "Other")
        s = entry.get("status", "Plan to Watch")
        badge_row.addWidget(_badge(t, TYPE_COLORS.get(t, "#607d8b")))
        badge_row.addWidget(_badge(s[:9], STATUS_COLORS.get(s, "#95a5a6")))
        layout.addLayout(badge_row)

        # Progress info
        current_ep = entry.get("current_episode", 0)
        total_eps = entry.get("episodes", 1)
        prog_lbl = QLabel(f"Prog: {current_ep} / {total_eps}")
        prog_lbl.setAlignment(Qt.AlignCenter)
        prog_lbl.setStyleSheet("color:#888; font-size:10px; border:none;")
        layout.addWidget(prog_lbl)

        # Rating stars
        rating = entry.get("rating", 0)
        if rating:
            stars = "★" * rating + "☆" * (10 - rating)
            r_lbl = QLabel(stars[:10])
            r_lbl.setAlignment(Qt.AlignCenter)
            r_lbl.setStyleSheet("color:#f1c40f;font-size:9px;border:none;")
            layout.addWidget(r_lbl, alignment=Qt.AlignHCenter)

        # Quick Actions row
        local_file_path = entry.get("local_file", "")
        web_link_url = entry.get("web_link", "")

        if local_file_path or web_link_url:
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(6)
            actions_layout.setAlignment(Qt.AlignCenter)

            if local_file_path:
                file_btn = QPushButton("📁 File")
                file_btn.setToolTip(f"Open location: {local_file_path}")
                file_btn.setStyleSheet(
                    "QPushButton { background:#2f3136; color:#00bcd4; border:1px solid #00bcd4; "
                    "border-radius:4px; padding:2px 6px; font-size:10px; font-weight:bold; }"
                    "QPushButton:hover { background:#00bcd4; color:black; }"
                )
                file_btn.clicked.connect(
                    lambda _, path=local_file_path: open_file_location(path)
                )
                actions_layout.addWidget(file_btn)

            if web_link_url:
                link_btn = QPushButton("🌐 Link")
                link_btn.setToolTip(f"Open link: {web_link_url}")
                link_btn.setStyleSheet(
                    "QPushButton { background:#2f3136; color:#9b59b6; border:1px solid #9b59b6; "
                    "border-radius:4px; padding:2px 6px; font-size:10px; font-weight:bold; }"
                    "QPushButton:hover { background:#9b59b6; color:white; }"
                )
                link_btn.clicked.connect(lambda _, url=web_link_url: open_web_link(url))
                actions_layout.addWidget(link_btn)

            layout.addLayout(actions_layout)

    def _apply_thumbnail(self, path: str):
        self.thumb_label.set_image_path(path)
        if path and Path(path).exists():
            px = QPixmap(path).scaled(
                THUMB_SIZE, THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.thumb_label.setPixmap(px)
        else:
            self.thumb_label.setText(PLACEHOLDER)
            self.thumb_label.setStyleSheet(
                "font-size:48px;color:#4f545c;background:#23272a;border-radius:6px;border:none;"
            )

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.clicked.emit(self._id)

    def _show_context_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )

        edit_act = QAction("✎ Edit Details", self)
        edit_act.triggered.connect(lambda: self.clicked.emit(self._id))
        menu.addAction(edit_act)

        add_act = QAction("＋ Add New Content", self)
        add_act.triggered.connect(lambda: self.add_requested.emit())
        menu.addAction(add_act)

        local_file = self.entry.get("local_file", "")
        web_link = self.entry.get("web_link", "")
        if local_file or web_link:
            menu.addSeparator()
            if local_file:
                file_act = QAction("📁 Open File Location", self)
                file_act.triggered.connect(
                    lambda _, path=local_file: open_file_location(path)
                )
                menu.addAction(file_act)
            if web_link:
                link_act = QAction("🌐 Open Web Link", self)
                link_act.triggered.connect(lambda _, url=web_link: open_web_link(url))
                menu.addAction(link_act)

        img_path = self.entry.get("image_path", "")
        if img_path:
            menu.addSeparator()
            open_img_loc_act = QAction("📂 Open Image Location", self)
            open_img_loc_act.triggered.connect(
                lambda _, path=img_path: open_file_location(path)
            )
            menu.addAction(open_img_loc_act)

            remove_img_act = QAction("🖼 Delete / Remove Image", self)
            remove_img_act.triggered.connect(
                lambda: self.image_remove_requested.emit(self._id)
            )
            menu.addAction(remove_img_act)

        menu.addSeparator()

        del_act = QAction("🗑 Remove Content", self)
        del_act.triggered.connect(lambda: self.delete_requested.emit(self._id))
        menu.addAction(del_act)

        menu.exec(self.mapToGlobal(pos))


# -------------------------------------------------------------------
# Card widget (Entity Listings)
# -------------------------------------------------------------------
class _EntityCard(QWidget):
    clicked = Signal(str)  # entity id
    delete_requested = Signal(str)  # entity id
    add_requested = Signal()

    def __init__(self, entity: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.entity = entity
        self._id = entity["id"]
        self.setFixedSize(CARD_SIZE + 10, CARD_SIZE + 50)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("entity_card")
        self.setStyleSheet(
            "QWidget#entity_card{background:#2c2f33;border:2px solid #4f545c;"
            "border-radius:8px;}"
            "QWidget#entity_card:hover{border:2px solid #00bcd4;}"
        )
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail
        self.thumb_label = DoubleClickableLabel()
        self.thumb_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("border:none;")
        self._apply_thumbnail(entity.get("image_path", ""))
        layout.addWidget(self.thumb_label, alignment=Qt.AlignHCenter)

        # Name
        name_lbl = QLabel(entity.get("name", "Unnamed"))
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setWordWrap(False)
        name_lbl.setStyleSheet(
            "color:#ffffff;font-weight:bold;font-size:11px;border:none;"
        )
        name_lbl.setFixedWidth(CARD_SIZE - 4)
        fm = name_lbl.fontMetrics()
        name_lbl.setText(
            fm.elidedText(entity.get("name", "Unnamed"), Qt.ElideRight, CARD_SIZE - 10)
        )
        name_lbl.setToolTip(entity.get("name", ""))
        layout.addWidget(name_lbl, alignment=Qt.AlignHCenter)

        # Badges row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(4)
        t = entity.get("type", "Other")
        r = entity.get("role", "Other")
        badge_row.addWidget(_badge(t, ENTITY_TYPE_COLORS.get(t, "#607d8b")))
        badge_row.addWidget(_badge(r[:9], ENTITY_ROLE_COLORS.get(r, "#607d8b")))
        layout.addLayout(badge_row)

        # Associated content or credits count
        credits = entity.get("credit_list", [])
        assoc = entity.get("associated_content", "")
        if credits:
            info_text = f"Credits: {len(credits)}"
        elif assoc:
            info_text = assoc
        else:
            info_text = ""

        if info_text:
            info_lbl = QLabel(info_text)
            info_lbl.setAlignment(Qt.AlignCenter)
            info_lbl.setStyleSheet("color:#888; font-size:10px; border:none;")
            info_lbl.setFixedWidth(CARD_SIZE - 10)
            info_lbl.setText(fm.elidedText(info_text, Qt.ElideRight, CARD_SIZE - 10))
            layout.addWidget(info_lbl, alignment=Qt.AlignHCenter)

        # Rating stars
        rating = entity.get("rating", 0)
        if rating:
            stars = "★" * rating + "☆" * (10 - rating)
            r_lbl = QLabel(stars[:10])
            r_lbl.setAlignment(Qt.AlignCenter)
            r_lbl.setStyleSheet("color:#f1c40f;font-size:9px;border:none;")
            layout.addWidget(r_lbl, alignment=Qt.AlignHCenter)

    def _apply_thumbnail(self, path: str):
        self.thumb_label.set_image_path(path)
        if path and Path(path).exists():
            px = QPixmap(path).scaled(
                THUMB_SIZE, THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.thumb_label.setPixmap(px)
        else:
            self.thumb_label.setText(ENTITY_PLACEHOLDER)
            self.thumb_label.setStyleSheet(
                "font-size:48px;color:#4f545c;background:#23272a;border-radius:6px;border:none;"
            )

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.clicked.emit(self._id)

    def _show_context_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )

        edit_act = QAction("✎ Edit Details", self)
        edit_act.triggered.connect(lambda: self.clicked.emit(self._id))
        menu.addAction(edit_act)

        add_act = QAction("＋ Add New Entity", self)
        add_act.triggered.connect(lambda: self.add_requested.emit())
        menu.addAction(add_act)

        img_path = self.entity.get("image_path", "")
        if img_path:
            menu.addSeparator()
            open_img_loc_act = QAction("📂 Open Image Location", self)
            open_img_loc_act.triggered.connect(
                lambda _, path=img_path: open_file_location(path)
            )
            menu.addAction(open_img_loc_act)

        menu.addSeparator()

        del_act = QAction("🗑 Remove Entity", self)
        del_act.triggered.connect(lambda: self.delete_requested.emit(self._id))
        menu.addAction(del_act)

        menu.exec(self.mapToGlobal(pos))


# -------------------------------------------------------------------
# Detail / edit panel (Content Listings)
# -------------------------------------------------------------------
class _DetailPanel(QWidget):
    saved = Signal(dict)
    deleted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entry_id: Optional[str] = None
        self._image_path = ""
        self._episode_data = []
        self._mal_worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Image picker
        img_row = QHBoxLayout()
        self.img_preview = DoubleClickableLabel()
        self.img_preview.setFixedSize(160, 160)
        self.img_preview.setAlignment(Qt.AlignCenter)
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
        )
        img_row.addWidget(self.img_preview)

        img_btns_layout = QVBoxLayout()
        img_btns_layout.setSpacing(6)
        img_btns_layout.setAlignment(Qt.AlignTop)

        browse_btn = QPushButton("📁 Browse Image")
        browse_btn.clicked.connect(self._browse_image)
        browse_btn.setFixedWidth(140)
        img_btns_layout.addWidget(browse_btn)

        self.btn_gen_thumb = QPushButton("⚡ Gen Thumbnail")
        self.btn_gen_thumb.setToolTip(
            "Extract thumbnail/cover from the associated Local File"
        )
        self.btn_gen_thumb.clicked.connect(self._generate_thumbnail)
        self.btn_gen_thumb.setFixedWidth(140)
        img_btns_layout.addWidget(self.btn_gen_thumb)

        self.btn_mal = QPushButton("Auto-Fill from MAL")
        self.btn_mal.setToolTip("Fetch metadata from MyAnimeList via Jikan API (Anime only)")
        self.btn_mal.setFixedWidth(140)
        self.btn_mal.setStyleSheet(
            "QPushButton { background-color:#1565c0; color:white; font-weight:bold;"
            " padding:6px 8px; border-radius:6px; border:none; }"
            "QPushButton:hover { background-color:#1976d2; }"
            "QPushButton:pressed { background-color:#0d47a1; }"
            "QPushButton:disabled { background-color:#37474f; color:#78909c; }"
        )
        self.btn_mal.clicked.connect(self._on_fetch_mal_clicked)
        img_btns_layout.addWidget(self.btn_mal)

        img_row.addLayout(img_btns_layout)
        img_row.addStretch()
        layout.addLayout(img_row)

        # Form
        form = QFormLayout()
        form.setSpacing(8)

        self.f_title = QLineEdit()
        self.f_title.setPlaceholderText("e.g. Cowboy Bebop")
        self.f_type = QComboBox()
        self.f_type.addItems(ENTRY_TYPES)
        # "Anime" is ENTRY_TYPES[0] so the button starts enabled by default
        self.btn_mal.setEnabled(self.f_type.currentText() == "Anime")
        self.f_type.currentTextChanged.connect(
            lambda text: self.btn_mal.setEnabled(text == "Anime")
        )
        self.f_status = QComboBox()
        self.f_status.addItems(ENTRY_STATUS)
        self.f_rating = QSpinBox()
        self.f_rating.setRange(0, 10)
        self.f_rating.setSpecialValueText("No rating")
        self.f_year = QSpinBox()
        self.f_year.setRange(0, 2100)
        self.f_year.setValue(0)
        self.f_year.setSpecialValueText("Unknown")
        self.f_episodes = QSpinBox()
        self.f_episodes.setRange(1, 99999)
        self.f_current_episode = QSpinBox()
        self.f_current_episode.setRange(0, 99999)
        self.f_episodes.valueChanged.connect(lambda val: self.f_current_episode.setRange(0, max(0, val)))
        self.f_genres = QLineEdit()
        self.f_genres.setPlaceholderText("e.g. Action, Drama")

        self.f_tags = QLineEdit()
        self.f_tags.setPlaceholderText("e.g. Space Cowboy, Sci-Fi")

        # Associated Entities selection row
        self.assoc_entities_ids = []
        self.f_assoc_entities_display = QLineEdit()
        self.f_assoc_entities_display.setReadOnly(True)
        self.f_assoc_entities_display.setPlaceholderText("None selected")

        self.btn_select_entities = QPushButton("🔗 Select Entities")
        self.btn_select_entities.clicked.connect(self._select_associated_entities)

        assoc_row = QHBoxLayout()
        assoc_row.addWidget(self.f_assoc_entities_display, 1)
        assoc_row.addWidget(self.btn_select_entities)

        # Local File and Web Link rows
        self.f_local_file = QLineEdit()
        self.f_local_file.setPlaceholderText("Select/paste local file path…")
        self.btn_browse_local_file = QPushButton("📁 Browse")
        self.btn_browse_local_file.clicked.connect(self._browse_local_file)
        self.btn_open_local_file = QPushButton("🚀 Open Location")
        self.btn_open_local_file.clicked.connect(self._open_local_file)

        local_file_row = QHBoxLayout()
        local_file_row.addWidget(self.f_local_file, 1)
        local_file_row.addWidget(self.btn_browse_local_file)
        local_file_row.addWidget(self.btn_open_local_file)

        self.f_web_link = QLineEdit()
        self.f_web_link.setPlaceholderText("Enter web URL (e.g. mal.net/anime/1)…")
        self.btn_open_web_link = QPushButton("🌐 Open Link")
        self.btn_open_web_link.clicked.connect(self._open_web_link)

        web_link_row = QHBoxLayout()
        web_link_row.addWidget(self.f_web_link, 1)
        web_link_row.addWidget(self.btn_open_web_link)

        self.f_review = QTextEdit()
        self.f_review.setPlaceholderText("Optional review or notes…")
        self.f_review.setFixedHeight(100)

        form.addRow("Title *", self.f_title)
        form.addRow("Type", self.f_type)
        form.addRow("Status", self.f_status)
        form.addRow("Rating (0-10)", self.f_rating)
        form.addRow("Year", self.f_year)
        form.addRow("Episodes / Pages", self.f_episodes)
        form.addRow("Current Episode / Page", self.f_current_episode)
        form.addRow("Genres", self.f_genres)
        form.addRow("Tags", self.f_tags)
        form.addRow("Associated Entities", assoc_row)
        form.addRow("Local File", local_file_row)
        form.addRow("Web Link", web_link_row)
        form.addRow("Review / Notes", self.f_review)
        layout.addLayout(form)

        # --- Episode List Section ---
        self.episode_group = QGroupBox("Episodes / Chapters / Parts")
        self.episode_group.setStyleSheet("QGroupBox{font-weight:bold; color:#00bcd4;}")
        eg_layout = QVBoxLayout(self.episode_group)

        self.ep_list_layout = QVBoxLayout()
        self.ep_list_layout.setSpacing(4)
        eg_layout.addLayout(self.ep_list_layout)

        add_ep_btn = QPushButton("＋ Add Episode Entry")
        add_ep_btn.clicked.connect(self._add_episode)
        eg_layout.addWidget(add_ep_btn)
        layout.addWidget(self.episode_group)

        # Action buttons
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        self.save_btn.clicked.connect(self._on_save)
        apply_shadow_effect(self.save_btn)

        self.del_btn = QPushButton("🗑 Delete")
        self.del_btn.setStyleSheet(
            "QPushButton{background:#c0392b;color:white;font-weight:bold;"
            "padding:10px;border-radius:8px;}"
            "QPushButton:hover{background:#e74c3c;}"
        )
        self.del_btn.clicked.connect(self._on_delete)
        apply_shadow_effect(self.del_btn)

        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.del_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

    def _select_associated_entities(self):
        all_entities = []
        try:
            if ENTITIES_FILE.exists():
                with open(ENTITIES_FILE, "r", encoding="utf-8") as f:
                    all_entities = json.load(f)
        except Exception as e:
            print(f"Failed to load entities for association: {e}")

        if not all_entities:
            QMessageBox.information(
                self,
                "No Entities Available",
                "There are no entities available in Entity Listings. Please add people or organizations first.",
            )
            return

        dlg = AssociatedEntitiesDialog(
            all_entities, self.assoc_entities_ids, parent=self
        )
        if dlg.exec():
            self.assoc_entities_ids = dlg.get_selected_ids()
            self._update_assoc_entities_display(all_entities)

    def _update_assoc_entities_display(self, all_entities: List[Dict[str, Any]]):
        names = []
        entity_map = {e["id"]: e["name"] for e in all_entities}
        for ent_id in self.assoc_entities_ids:
            if ent_id in entity_map:
                names.append(entity_map[ent_id])
        self.f_assoc_entities_display.setText(", ".join(names))

    def load_entry(self, entry: Dict[str, Any]):
        self._entry_id = entry.get("id")
        self._image_path = entry.get("image_path", "")
        self.f_title.setText(entry.get("title", ""))
        self.f_type.setCurrentText(entry.get("type", "Anime"))
        self.f_status.setCurrentText(entry.get("status", "Plan to Watch"))
        self.f_rating.setValue(entry.get("rating", 0))
        self.f_year.setValue(entry.get("year", 0))
        self.f_episodes.setValue(entry.get("episodes", 1))
        self.f_current_episode.setValue(entry.get("current_episode", 0))
        self.f_genres.setText(entry.get("genres", ""))

        # Tags and Associated Entities
        self.f_tags.setText(entry.get("tags", ""))
        self.assoc_entities_ids = entry.get("associated_entities", [])

        self.f_local_file.setText(entry.get("local_file", ""))
        self.f_web_link.setText(entry.get("web_link", ""))

        all_entities = []
        try:
            if ENTITIES_FILE.exists():
                with open(ENTITIES_FILE, "r", encoding="utf-8") as f:
                    all_entities = json.load(f)
        except Exception as e:
            print(f"Failed to load entities: {e}")
        self._update_assoc_entities_display(all_entities)

        self.f_review.setPlainText(entry.get("review", ""))
        self._episode_data = entry.get("episode_list", [])
        self._refresh_image()
        self._refresh_episode_list()
        self.del_btn.setVisible(True)
        self.episode_group.setVisible(True)

    def clear_for_new(self):
        self._entry_id = None
        self._image_path = ""
        self._episode_data = []
        self.f_title.clear()
        self.f_type.setCurrentIndex(0)
        self.f_status.setCurrentIndex(0)
        self.f_rating.setValue(0)
        self.f_year.setValue(0)
        self.f_episodes.setValue(1)
        self.f_current_episode.setValue(0)
        self.f_genres.clear()

        self.f_tags.clear()
        self.assoc_entities_ids = []
        self.f_assoc_entities_display.clear()
        self.f_local_file.clear()
        self.f_web_link.clear()

        self.f_review.clear()
        self.img_preview.clear()
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
        )
        self._refresh_episode_list()
        self.del_btn.setVisible(False)
        self.episode_group.setVisible(False)

    def _browse_local_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Local File",
            "",
            "All Files (*.*)",
        )
        if path:
            self.f_local_file.setText(path)

    def _open_local_file(self):
        path = self.f_local_file.text().strip()
        if not path:
            QMessageBox.warning(
                self, "No File", "Please select or enter a local file path first."
            )
            return
        p = Path(path)
        if not p.exists():
            QMessageBox.warning(
                self, "File Not Found", f"The file at '{path}' does not exist."
            )
            return
        open_file_location(path)

    def _open_web_link(self):
        url = self.f_web_link.text().strip()
        if not url:
            QMessageBox.warning(self, "No Link", "Please enter a web link first.")
            return
        open_web_link(url)

    def _generate_thumbnail(self):
        file_path = self.f_local_file.text().strip()
        if not file_path:
            QMessageBox.warning(
                self,
                "No Local File",
                "Please specify a valid Local File first to generate a thumbnail.",
            )
            return

        p = Path(file_path)
        if not p.exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The local file at '{file_path}' does not exist.",
            )
            return

        suffix = p.suffix.lower()
        LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        self._entry_id = self._entry_id or str(uuid.uuid4())
        dest_p = LISTING_IMAGES_DIR / f"{self._entry_id}.png"

        # Image formats - shortcut direct copy
        if suffix in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
            import shutil

            try:
                shutil.copy2(file_path, dest_p)
                self._image_path = str(dest_p.absolute())
                self._refresh_image()
                QMessageBox.information(
                    self, "Success", "Image set as thumbnail successfully!"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to set image: {e}")
            return

        # Video / PDF formats - selection dialog
        if suffix in (".pdf", ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v"):
            dlg = ThumbnailSelectionDialog(file_path, parent=self)
            if dlg.exec() == QDialog.Accepted and dlg.selected_image:
                if dlg.selected_image.save(str(dest_p.absolute())):
                    self._image_path = str(dest_p.absolute())
                    self._refresh_image()
                    QMessageBox.information(
                        self,
                        "Success",
                        "Successfully saved selected representative thumbnail!",
                    )
                else:
                    QMessageBox.critical(
                        self, "Error", "Failed to save selected thumbnail image."
                    )
            return

        QMessageBox.warning(
            self,
            "Unsupported Format",
            "This file format is not supported for generating a thumbnail.",
        )

    @Slot()
    def _on_fetch_mal_clicked(self):
        from ...helpers.web.mal_sync_worker import MalSyncWorker

        title = self.f_title.text().strip()
        if not title:
            QMessageBox.warning(
                self, "No Title", "Please enter a title before fetching from MAL."
            )
            return
        self.btn_mal.setText("Fetching...")
        self.btn_mal.setEnabled(False)
        self._mal_worker = MalSyncWorker(title)
        self._mal_worker.finished.connect(self._on_mal_finished)
        self._mal_worker.error.connect(self._on_mal_error)
        self._mal_worker.start()

    @Slot(dict)
    def _on_mal_finished(self, data: dict):
        synopsis = data.get("synopsis", "")
        if synopsis:
            self.f_review.setPlainText(synopsis)
        episodes = data.get("episodes")
        if episodes:
            self.f_episodes.setValue(int(episodes))
        score = data.get("score")
        if score:
            self.f_rating.setValue(int(score))
        genres = data.get("genres", "")
        if genres:
            self.f_genres.setText(genres)
        year = data.get("year")
        if year:
            self.f_year.setValue(int(year))
        mapped_status = data.get("status", "")
        if mapped_status and mapped_status in ENTRY_STATUS:
            self.f_status.setCurrentText(mapped_status)
        self.btn_mal.setText("Auto-Fill from MAL")
        self.btn_mal.setEnabled(True)

    @Slot(str)
    def _on_mal_error(self, message: str):
        QMessageBox.critical(self, "MAL Fetch Error", message)
        self.btn_mal.setText("Auto-Fill from MAL")
        self.btn_mal.setEnabled(True)

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if path:
            import shutil

            LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            self._entry_id = self._entry_id or str(uuid.uuid4())
            orig_p = Path(path)
            dest_p = LISTING_IMAGES_DIR / f"{self._entry_id}{orig_p.suffix}"
            try:
                shutil.copy2(path, dest_p)
                self._image_path = str(dest_p.absolute())
            except Exception as e:
                print(f"Failed to copy image: {e}")
                self._image_path = path
            self._refresh_image()

    def _refresh_image(self):
        self.img_preview.set_image_path(self._image_path)
        if self._image_path and Path(self._image_path).exists():
            px = QPixmap(self._image_path).scaled(
                160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.img_preview.setPixmap(px)
            self.img_preview.setStyleSheet(
                "border:2px solid #4f545c;border-radius:8px;"
            )
        else:
            self.img_preview.clear()
            self.img_preview.setText("No Image")
            self.img_preview.setStyleSheet(
                "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
            )

    def _refresh_episode_list(self):
        while self.ep_list_layout.count():
            item = self.ep_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sorted_eps = sorted(self._episode_data, key=lambda x: x.get("number", 0))

        for ep in sorted_eps:
            row = QFrame()
            row.setStyleSheet(
                "QFrame{background:#23272a; border-radius:4px; padding:2px;}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(6, 4, 6, 4)

            num = ep.get("number", 0)
            title = ep.get("title", "")
            rating = ep.get("rating", 0)
            img_path = ep.get("image_path", "")

            # Thumbnail
            t_lbl = QLabel()
            t_lbl.setFixedSize(50, 40)
            t_lbl.setAlignment(Qt.AlignCenter)
            t_lbl.setStyleSheet("background:#1a1c1e; border-radius:3px;")
            if img_path and Path(img_path).exists():
                px = QPixmap(img_path).scaled(
                    50, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                t_lbl.setPixmap(px)
            else:
                t_lbl.setText("No Img")
                t_lbl.setStyleSheet(
                    "background:#1a1c1e; border-radius:3px; color:#555; font-size:8px;"
                )
            rl.addWidget(t_lbl)
            info = QLabel(f"<b>#{num}</b> {title}")
            rl.addWidget(info, 1)
            if rating:
                r_lbl = QLabel("★" * rating)
                r_lbl.setStyleSheet("color:#f1c40f; font-size:10px;")
                rl.addWidget(r_lbl)

            # Local File & Web Link shortcuts
            local_file = ep.get("local_file", "")
            web_link = ep.get("web_link", "")

            if local_file:
                file_btn = QPushButton("📁")
                file_btn.setFixedSize(24, 24)
                file_btn.setToolTip(f"Open: {local_file}")
                file_btn.setStyleSheet(
                    "background-color:#16a085; color:white; font-size:10px; font-weight:bold; border-radius:3px;"
                )
                file_btn.clicked.connect(
                    lambda _, path=local_file: open_file_location(path)
                )
                rl.addWidget(file_btn)

            if web_link:
                link_btn = QPushButton("🌐")
                link_btn.setFixedSize(24, 24)
                link_btn.setToolTip(f"Open Link: {web_link}")
                link_btn.setStyleSheet(
                    "background-color:#2980b9; color:white; font-size:10px; font-weight:bold; border-radius:3px;"
                )
                link_btn.clicked.connect(lambda _, url=web_link: open_web_link(url))
                rl.addWidget(link_btn)

            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(24, 24)
            edit_btn.setToolTip("Edit episode")
            edit_btn.clicked.connect(lambda _, e=ep: self._edit_episode(e))
            rl.addWidget(edit_btn)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setToolTip("Remove episode record")
            del_btn.clicked.connect(lambda _, eid=ep["id"]: self._remove_episode(eid))
            rl.addWidget(del_btn)

            self.ep_list_layout.addWidget(row)

    def _add_episode(self):
        dlg = EpisodeDialog(parent=self)
        if dlg.exec():
            new_ep = dlg.get_data()
            self._episode_data.append(new_ep)
            self._refresh_episode_list()

    def _edit_episode(self, ep_data: Dict[str, Any]):
        dlg = EpisodeDialog(ep_data, parent=self)
        if dlg.exec():
            updated = dlg.get_data()
            for i, e in enumerate(self._episode_data):
                if e["id"] == updated["id"]:
                    self._episode_data[i] = updated
                    break
            self._refresh_episode_list()

    def _remove_episode(self, ep_id: str):
        self._episode_data = [e for e in self._episode_data if e["id"] != ep_id]
        self._refresh_episode_list()

    def _collect(self) -> Optional[Dict[str, Any]]:
        title = self.f_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Missing Title", "Please enter a title.")
            return None
        return {
            "id": self._entry_id or str(uuid.uuid4()),
            "title": title,
            "type": self.f_type.currentText(),
            "status": self.f_status.currentText(),
            "rating": self.f_rating.value(),
            "year": self.f_year.value(),
            "episodes": self.f_episodes.value(),
            "current_episode": self.f_current_episode.value(),
            "genres": self.f_genres.text().strip(),
            "tags": self.f_tags.text().strip(),
            "associated_entities": self.assoc_entities_ids,
            "local_file": self.f_local_file.text().strip(),
            "web_link": self.f_web_link.text().strip(),
            "review": self.f_review.toPlainText().strip(),
            "image_path": self._image_path,
            "episode_list": self._episode_data,
            "date_added": str(date.today()),
        }

    @Slot()
    def _on_save(self):
        entry = self._collect()
        if entry:
            self.saved.emit(entry)

    @Slot()
    def _on_delete(self):
        if not self._entry_id:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entry from your listings?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.deleted.emit(self._entry_id)


# -------------------------------------------------------------------
# Detail / edit panel (Entity Listings)
# -------------------------------------------------------------------
class _EntityDetailPanel(QWidget):
    saved = Signal(dict)
    deleted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entity_id: Optional[str] = None
        self._image_path = ""
        self._credit_data = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Image picker
        img_row = QHBoxLayout()
        self.img_preview = DoubleClickableLabel()
        self.img_preview.setFixedSize(160, 160)
        self.img_preview.setAlignment(Qt.AlignCenter)
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
        )
        img_row.addWidget(self.img_preview)
        browse_btn = QPushButton("📁 Browse Image")
        browse_btn.clicked.connect(self._browse_image)
        browse_btn.setFixedWidth(130)
        img_row.addWidget(browse_btn, alignment=Qt.AlignTop)
        img_row.addStretch()
        layout.addLayout(img_row)

        # Form
        form = QFormLayout()
        form.setSpacing(8)

        self.f_name = QLineEdit()
        self.f_name.setPlaceholderText("e.g. Hayao Miyazaki")

        self.f_type = QComboBox()
        self.f_type.addItems(ENTITY_TYPES)

        self.f_role = QComboBox()
        self.f_role.addItems(ENTITY_ROLES)

        self.f_rating = QSpinBox()
        self.f_rating.setRange(0, 10)
        self.f_rating.setSpecialValueText("No rating")

        self.f_year = QSpinBox()
        self.f_year.setRange(0, 2100)
        self.f_year.setValue(0)
        self.f_year.setSpecialValueText("Unknown")

        self.f_associated = QLineEdit()
        self.f_associated.setPlaceholderText("Main Associated Work / Studio")

        self.f_notes = QTextEdit()
        self.f_notes.setPlaceholderText("Biography or notes…")
        self.f_notes.setFixedHeight(100)

        form.addRow("Name *", self.f_name)
        form.addRow("Type", self.f_type)
        form.addRow("Role", self.f_role)
        form.addRow("Rating (0-10)", self.f_rating)
        form.addRow("Debut Year", self.f_year)
        form.addRow("Associated Content", self.f_associated)
        form.addRow("Biography / Notes", self.f_notes)
        layout.addLayout(form)

        # --- Credit List Section ---
        self.credits_group = QGroupBox("Works / Credits / Appearances")
        self.credits_group.setStyleSheet("QGroupBox{font-weight:bold; color:#00bcd4;}")
        cg_layout = QVBoxLayout(self.credits_group)

        self.credit_list_layout = QVBoxLayout()
        self.credit_list_layout.setSpacing(4)
        cg_layout.addLayout(self.credit_list_layout)

        add_credit_btn = QPushButton("＋ Add Credit Entry")
        add_credit_btn.clicked.connect(self._add_credit)
        cg_layout.addWidget(add_credit_btn)
        layout.addWidget(self.credits_group)

        # Action buttons
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        self.save_btn.clicked.connect(self._on_save)
        apply_shadow_effect(self.save_btn)

        self.del_btn = QPushButton("🗑 Delete")
        self.del_btn.setStyleSheet(
            "QPushButton{background:#c0392b;color:white;font-weight:bold;"
            "padding:10px;border-radius:8px;}"
            "QPushButton:hover{background:#e74c3c;}"
        )
        self.del_btn.clicked.connect(self._on_delete)
        apply_shadow_effect(self.del_btn)

        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.del_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

    def load_entity(self, entity: Dict[str, Any]):
        self._entity_id = entity.get("id")
        self._image_path = entity.get("image_path", "")
        self.f_name.setText(entity.get("name", ""))
        self.f_type.setCurrentText(entity.get("type", "Person"))
        self.f_role.setCurrentText(entity.get("role", "Director"))
        self.f_rating.setValue(entity.get("rating", 0))
        self.f_year.setValue(entity.get("year", 0))
        self.f_associated.setText(entity.get("associated_content", ""))
        self.f_notes.setPlainText(entity.get("notes", ""))
        self._credit_data = entity.get("credit_list", [])
        self._refresh_image()
        self._refresh_credit_list()
        self.del_btn.setVisible(True)
        self.credits_group.setVisible(True)

    def clear_for_new(self):
        self._entity_id = None
        self._image_path = ""
        self._credit_data = []
        self.f_name.clear()
        self.f_type.setCurrentIndex(0)
        self.f_role.setCurrentIndex(0)
        self.f_rating.setValue(0)
        self.f_year.setValue(0)
        self.f_associated.clear()
        self.f_notes.clear()
        self.img_preview.clear()
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet(
            "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
        )
        self._refresh_credit_list()
        self.del_btn.setVisible(False)
        self.credits_group.setVisible(False)

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if path:
            import shutil

            LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            self._entity_id = self._entity_id or str(uuid.uuid4())
            orig_p = Path(path)
            dest_p = LISTING_IMAGES_DIR / f"{self._entity_id}{orig_p.suffix}"
            try:
                shutil.copy2(path, dest_p)
                self._image_path = str(dest_p.absolute())
            except Exception as e:
                print(f"Failed to copy image: {e}")
                self._image_path = path
            self._refresh_image()

    def _refresh_image(self):
        self.img_preview.set_image_path(self._image_path)
        if self._image_path and Path(self._image_path).exists():
            px = QPixmap(self._image_path).scaled(
                160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.img_preview.setPixmap(px)
            self.img_preview.setStyleSheet(
                "border:2px solid #4f545c;border-radius:8px;"
            )
        else:
            self.img_preview.clear()
            self.img_preview.setText("No Image")
            self.img_preview.setStyleSheet(
                "border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;"
            )

    def _refresh_credit_list(self):
        while self.credit_list_layout.count():
            item = self.credit_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sorted_credits = sorted(
            self._credit_data, key=lambda x: x.get("year", 0), reverse=True
        )

        for cr in sorted_credits:
            row = QFrame()
            row.setStyleSheet(
                "QFrame{background:#23272a; border-radius:4px; padding:2px;}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(6, 4, 6, 4)

            title = cr.get("title", "Untitled")
            role = cr.get("role", "")
            year = cr.get("year", 0)
            rating = cr.get("rating", 0)
            img_path = cr.get("image_path", "")

            # Thumbnail
            t_lbl = QLabel()
            t_lbl.setFixedSize(50, 40)
            t_lbl.setAlignment(Qt.AlignCenter)
            t_lbl.setStyleSheet("background:#1a1c1e; border-radius:3px;")
            if img_path and Path(img_path).exists():
                px = QPixmap(img_path).scaled(
                    50, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                t_lbl.setPixmap(px)
            else:
                t_lbl.setText("No Img")
                t_lbl.setStyleSheet(
                    "background:#1a1c1e; border-radius:3px; color:#555; font-size:8px;"
                )
            rl.addWidget(t_lbl)

            role_part = f" as <i>{role}</i>" if role else ""
            year_part = f" ({year})" if year else ""
            info = QLabel(f"<b>{title}</b>{role_part}{year_part}")
            rl.addWidget(info, 1)
            if rating:
                r_lbl = QLabel("★" * rating)
                r_lbl.setStyleSheet("color:#f1c40f; font-size:10px;")
                rl.addWidget(r_lbl)

            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(24, 24)
            edit_btn.setToolTip("Edit credit")
            edit_btn.clicked.connect(lambda _, c=cr: self._edit_credit(c))
            rl.addWidget(edit_btn)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setToolTip("Remove credit record")
            del_btn.clicked.connect(lambda _, cid=cr["id"]: self._remove_credit(cid))
            rl.addWidget(del_btn)

            self.credit_list_layout.addWidget(row)

    def _add_credit(self):
        dlg = CreditDialog(parent=self)
        if dlg.exec():
            new_cr = dlg.get_data()
            self._credit_data.append(new_cr)
            self._refresh_credit_list()

    def _edit_credit(self, credit_data: Dict[str, Any]):
        dlg = CreditDialog(credit_data, parent=self)
        if dlg.exec():
            updated = dlg.get_data()
            for i, c in enumerate(self._credit_data):
                if c["id"] == updated["id"]:
                    self._credit_data[i] = updated
                    break
            self._refresh_credit_list()

    def _remove_credit(self, credit_id: str):
        self._credit_data = [c for c in self._credit_data if c["id"] != credit_id]
        self._refresh_credit_list()

    def _collect(self) -> Optional[Dict[str, Any]]:
        name = self.f_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a name.")
            return None
        return {
            "id": self._entity_id or str(uuid.uuid4()),
            "name": name,
            "type": self.f_type.currentText(),
            "role": self.f_role.currentText(),
            "rating": self.f_rating.value(),
            "year": self.f_year.value(),
            "associated_content": self.f_associated.text().strip(),
            "notes": self.f_notes.toPlainText().strip(),
            "image_path": self._image_path,
            "credit_list": self._credit_data,
            "date_added": str(date.today()),
        }

    @Slot()
    def _on_save(self):
        entity = self._collect()
        if entity:
            self.saved.emit(entity)

    @Slot()
    def _on_delete(self):
        if not self._entity_id:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entity from your listings?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.deleted.emit(self._entity_id)


class AdvancedSearchDialog(QDialog):
    def __init__(self, parent=None, entries=None, entities=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 Advanced Search Settings")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(
            "QDialog { background: #23272a; color: white; }"
            "QLabel { color: #00bcd4; font-weight: bold; font-size: 12px; }"
            "QListWidget { background: #2c2f33; border: 1px solid #4f545c; border-radius: 6px; color: white; }"
            "QListWidget::item:hover { background: #00bcd4; color: black; }"
            "QComboBox { background: #2c2f33; color: white; border: 1px solid #4f545c; border-radius: 4px; padding: 4px; }"
            "QTabWidget::pane { border: 1px solid #4f545c; background: #23272a; border-radius: 6px; }"
            "QTabBar::tab { background: #2c2f33; color: #888; padding: 8px 16px; border: 1px solid #4f545c; border-top-left-radius: 4px; border-top-right-radius: 4px; }"
            "QTabBar::tab:selected { background: #23272a; color: #00bcd4; border-bottom-color: #23272a; font-weight: bold; }"
        )

        self.entries = entries or []
        self.entities = entities or []

        # Extract unique tags & genres
        all_tags = set()
        all_genres = set()
        for e in self.entries:
            for t in e.get("tags", "").split(","):
                ts = t.strip()
                if ts:
                    all_tags.add(ts)
            for g in e.get("genres", "").split(","):
                gs = g.strip()
                if gs:
                    all_genres.add(gs)

        self.sorted_tags = sorted(list(all_tags), key=lambda x: x.lower())
        self.sorted_genres = sorted(list(all_genres), key=lambda x: x.lower())
        self.sorted_entities = sorted(self.entities, key=lambda x: x.get("name", "").lower())

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        header_title = QLabel("🔍 Advanced Content Search")
        header_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00bcd4;")
        header_layout.addWidget(header_title)
        layout.addLayout(header_layout)

        # Match mode combo
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Match Mode (Inclusions):")
        mode_label.setFixedWidth(180)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Match ALL positive criteria (AND)",
            "Match ANY positive criteria (OR)"
        ])
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)

        # Tab widget
        self.tabs = QTabWidget()
        
        # Tab 1: Entities
        ent_tab = QWidget()
        ent_layout = QHBoxLayout(ent_tab)
        ent_layout.setContentsMargins(8, 8, 8, 8)
        ent_layout.setSpacing(12)

        # Include Entities
        inc_ent_box = QVBoxLayout()
        inc_ent_box.addWidget(QLabel("👥 Include Entities:"))
        self.inc_ent_list = QListWidget()
        for ent in self.sorted_entities:
            item = QListWidgetItem(ent.get("name", "Unnamed"))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, ent.get("id"))
            self.inc_ent_list.addItem(item)
        inc_ent_box.addWidget(self.inc_ent_list)
        ent_layout.addLayout(inc_ent_box)

        # Exclude Entities
        exc_ent_box = QVBoxLayout()
        exc_ent_box.addWidget(QLabel("🚫 Exclude Entities:"))
        self.exc_ent_list = QListWidget()
        for ent in self.sorted_entities:
            item = QListWidgetItem(ent.get("name", "Unnamed"))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, ent.get("id"))
            self.exc_ent_list.addItem(item)
        exc_ent_box.addWidget(self.exc_ent_list)
        ent_layout.addLayout(exc_ent_box)

        self.tabs.addTab(ent_tab, "👥 Entities")

        # Tab 2: Tags
        tag_tab = QWidget()
        tag_layout = QHBoxLayout(tag_tab)
        tag_layout.setContentsMargins(8, 8, 8, 8)
        tag_layout.setSpacing(12)

        # Include Tags
        inc_tag_box = QVBoxLayout()
        inc_tag_box.addWidget(QLabel("🏷 Include Tags:"))
        self.inc_tag_list = QListWidget()
        for tag in self.sorted_tags:
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.inc_tag_list.addItem(item)
        inc_tag_box.addWidget(self.inc_tag_list)
        tag_layout.addLayout(inc_tag_box)

        # Exclude Tags
        exc_tag_box = QVBoxLayout()
        exc_tag_box.addWidget(QLabel("🚫 Exclude Tags:"))
        self.exc_tag_list = QListWidget()
        for tag in self.sorted_tags:
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.exc_tag_list.addItem(item)
        exc_tag_box.addWidget(self.exc_tag_list)
        tag_layout.addLayout(exc_tag_box)

        self.tabs.addTab(tag_tab, "🏷 Tags")

        # Tab 3: Genres
        genre_tab = QWidget()
        genre_layout = QHBoxLayout(genre_tab)
        genre_layout.setContentsMargins(8, 8, 8, 8)
        genre_layout.setSpacing(12)

        # Include Genres
        inc_genre_box = QVBoxLayout()
        inc_genre_box.addWidget(QLabel("🎭 Include Genres:"))
        self.inc_genre_list = QListWidget()
        for genre in self.sorted_genres:
            item = QListWidgetItem(genre)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.inc_genre_list.addItem(item)
        inc_genre_box.addWidget(self.inc_genre_list)
        genre_layout.addLayout(inc_genre_box)

        # Exclude Genres
        exc_genre_box = QVBoxLayout()
        exc_genre_box.addWidget(QLabel("🚫 Exclude Genres:"))
        self.exc_genre_list = QListWidget()
        for genre in self.sorted_genres:
            item = QListWidgetItem(genre)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.exc_genre_list.addItem(item)
        exc_genre_box.addWidget(self.exc_genre_list)
        genre_layout.addLayout(exc_genre_box)

        self.tabs.addTab(genre_tab, "🎭 Genres")

        layout.addWidget(self.tabs, 1)

        # Actions buttons
        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(12)
        btns_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.setStyleSheet(
            "QPushButton { background: #2f3136; color: white; border: 1px solid #4f545c; border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #4f545c; }"
        )
        self.cancel_btn.clicked.connect(self.reject)
        btns_layout.addWidget(self.cancel_btn)

        self.search_btn = QPushButton("Search")
        self.search_btn.setFixedWidth(120)
        self.search_btn.setStyleSheet(
            "QPushButton { background: #00bcd4; color: black; border: none; border-radius: 4px; padding: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #008ba3; color: white; }"
        )
        self.search_btn.clicked.connect(self.accept)
        btns_layout.addWidget(self.search_btn)

        layout.addLayout(btns_layout)

    def load_criteria(self, crit):
        if not crit:
            return
        
        # Set match mode
        if crit.get("match_mode") == "OR":
            self.mode_combo.setCurrentIndex(1)
        else:
            self.mode_combo.setCurrentIndex(0)

        # Set check states
        inc_ent = set(crit.get("include_entities", []))
        exc_ent = set(crit.get("exclude_entities", []))
        inc_tag = set(crit.get("include_tags", []))
        exc_tag = set(crit.get("exclude_tags", []))
        inc_genre = set(crit.get("include_genres", []))
        exc_genre = set(crit.get("exclude_genres", []))

        # Entities
        for idx in range(self.inc_ent_list.count()):
            item = self.inc_ent_list.item(idx)
            ent_id = item.data(Qt.UserRole)
            if ent_id in inc_ent:
                item.setCheckState(Qt.Checked)
        for idx in range(self.exc_ent_list.count()):
            item = self.exc_ent_list.item(idx)
            ent_id = item.data(Qt.UserRole)
            if ent_id in exc_ent:
                item.setCheckState(Qt.Checked)

        # Tags
        for idx in range(self.inc_tag_list.count()):
            item = self.inc_tag_list.item(idx)
            if item.text() in inc_tag:
                item.setCheckState(Qt.Checked)
        for idx in range(self.exc_tag_list.count()):
            item = self.exc_tag_list.item(idx)
            if item.text() in exc_tag:
                item.setCheckState(Qt.Checked)

        # Genres
        for idx in range(self.inc_genre_list.count()):
            item = self.inc_genre_list.item(idx)
            if item.text() in inc_genre:
                item.setCheckState(Qt.Checked)
        for idx in range(self.exc_genre_list.count()):
            item = self.exc_genre_list.item(idx)
            if item.text() in exc_genre:
                item.setCheckState(Qt.Checked)

    def get_criteria(self):
        crit = {
            "include_entities": [],
            "exclude_entities": [],
            "include_tags": [],
            "exclude_tags": [],
            "include_genres": [],
            "exclude_genres": [],
            "match_mode": "AND" if self.mode_combo.currentIndex() == 0 else "OR"
        }

        # Entities
        for idx in range(self.inc_ent_list.count()):
            item = self.inc_ent_list.item(idx)
            if item.checkState() == Qt.Checked:
                crit["include_entities"].append(item.data(Qt.UserRole))
        for idx in range(self.exc_ent_list.count()):
            item = self.exc_ent_list.item(idx)
            if item.checkState() == Qt.Checked:
                crit["exclude_entities"].append(item.data(Qt.UserRole))

        # Tags
        for idx in range(self.inc_tag_list.count()):
            item = self.inc_tag_list.item(idx)
            if item.checkState() == Qt.Checked:
                crit["include_tags"].append(item.text())
        for idx in range(self.exc_tag_list.count()):
            item = self.exc_tag_list.item(idx)
            if item.checkState() == Qt.Checked:
                crit["exclude_tags"].append(item.text())

        # Genres
        for idx in range(self.inc_genre_list.count()):
            item = self.inc_genre_list.item(idx)
            if item.checkState() == Qt.Checked:
                crit["include_genres"].append(item.text())
        for idx in range(self.exc_genre_list.count()):
            item = self.exc_genre_list.item(idx)
            if item.checkState() == Qt.Checked:
                crit["exclude_genres"].append(item.text())

        return crit


# -------------------------------------------------------------------
# Directory Import Dialog
# -------------------------------------------------------------------
class _DirectoryImportDialog(QDialog):
    """One-shot wizard: pick a directory of video files → review detected
    series → configure shared metadata → confirm or cancel import."""

    def __init__(self, existing_titles: "set[str]", parent=None):
        super().__init__(parent)
        self.setWindowTitle("📂 Import Listings from Video Directory")
        self.setMinimumSize(840, 620)
        self.setStyleSheet(
            "QDialog { background:#2c2f33; color:white; }"
            "QLabel  { color:white; }"
            "QLineEdit, QSpinBox, QComboBox { background:#23272a; color:white;"
            "  border:1px solid #4f545c; border-radius:4px; padding:4px; }"
            "QGroupBox { border:1px solid #4f545c; border-radius:6px;"
            "  margin-top:8px; color:#00bcd4; font-weight:bold; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }"
        )

        self._existing_titles = existing_titles  # lowercase normalised set
        self._scan_result: dict = {}             # {series_name: [(ep_num, path), ...]}
        self._directory = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # ── Directory picker row ──────────────────────────────────────
        dir_group = QGroupBox("Video Directory")
        dir_row = QHBoxLayout(dir_group)
        dir_row.setSpacing(6)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Select the folder that contains your video files…")
        self._dir_edit.setReadOnly(True)
        browse_btn = QPushButton("📁 Browse…")
        browse_btn.setFixedWidth(100)
        browse_btn.clicked.connect(self._browse)
        scan_btn = QPushButton("🔍 Scan")
        scan_btn.setFixedWidth(80)
        scan_btn.clicked.connect(self._do_scan)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse_btn)
        dir_row.addWidget(scan_btn)
        root.addWidget(dir_group)

        # ── Middle: table left | options right ────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left — detected-series table
        left = QWidget()
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(6)

        self._status_lbl = QLabel("Scan a directory to detect series.")
        self._status_lbl.setStyleSheet("color:#888; font-size:11px;")
        left_vbox.addWidget(self._status_lbl)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["", "Series Name", "Episodes", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 32)
        self._table.setColumnWidth(2, 72)
        self._table.setColumnWidth(3, 120)
        self._table.verticalHeader().hide()
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { background:#23272a; alternate-background-color:#252830;"
            "  border:1px solid #4f545c; border-radius:6px; gridline-color:#3a3d42; }"
            "QTableWidget::item { color:white; padding:3px; }"
            "QTableWidget::item:selected { background:#00bcd4; color:black; }"
            "QHeaderView::section { background:#2c2f33; color:#888; border:none; padding:4px; }"
        )
        left_vbox.addWidget(self._table, 1)

        sel_row = QHBoxLayout()
        sel_all_btn = QPushButton("☑ Select All New")
        sel_all_btn.setFixedHeight(26)
        sel_all_btn.clicked.connect(self._select_all_new)
        sel_none_btn = QPushButton("☐ Deselect All")
        sel_none_btn.setFixedHeight(26)
        sel_none_btn.clicked.connect(self._deselect_all)
        sel_row.addWidget(sel_all_btn)
        sel_row.addWidget(sel_none_btn)
        sel_row.addStretch()
        left_vbox.addLayout(sel_row)
        splitter.addWidget(left)

        # Right — metadata options
        right = QWidget()
        right_vbox = QVBoxLayout(right)
        right_vbox.setContentsMargins(6, 0, 0, 0)
        right_vbox.setSpacing(8)

        meta_group = QGroupBox("Metadata Applied to All New Entries")
        meta_form = QFormLayout(meta_group)
        meta_form.setSpacing(8)

        self._f_type = QComboBox()
        self._f_type.addItems(ENTRY_TYPES)
        self._f_type.setCurrentText("Anime")

        self._f_status = QComboBox()
        self._f_status.addItems(ENTRY_STATUS)
        self._f_status.setCurrentText("Plan to Watch")

        self._f_year = QSpinBox()
        self._f_year.setRange(0, 2100)
        self._f_year.setValue(0)
        self._f_year.setSpecialValueText("Unknown")

        self._f_genres = QLineEdit()
        self._f_genres.setPlaceholderText("e.g. Action, Comedy")

        self._f_tags = QLineEdit()
        self._f_tags.setPlaceholderText("e.g. subbed, seasonal")

        self._f_creator = QLineEdit()
        self._f_creator.setPlaceholderText("Studio / Author (optional)")

        meta_form.addRow("Type:", self._f_type)
        meta_form.addRow("Status:", self._f_status)
        meta_form.addRow("Year:", self._f_year)
        meta_form.addRow("Genres:", self._f_genres)
        meta_form.addRow("Tags:", self._f_tags)
        meta_form.addRow("Creator:", self._f_creator)
        right_vbox.addWidget(meta_group)
        right_vbox.addStretch()

        info_lbl = QLabel(
            "<small>"
            "<b>What gets created per series:</b><br>"
            "• Title from the filename prefix before <code> - </code><br>"
            "• <i>Episodes</i> count = number of matching files<br>"
            "• <i>Local File</i> = path to the first episode<br>"
            "• Individual episode entries, each with its own file path<br>"
            "• Episode number extracted from the filename<br><br>"
            "<b>Filename format expected:</b><br>"
            "<code>&lt;Series&gt; - &lt;##&gt; [suffix].ext</code>"
            "</small>"
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color:#888; font-size:10px; border:none;")
        right_vbox.addWidget(info_lbl)
        splitter.addWidget(right)

        splitter.setSizes([520, 300])
        root.addWidget(splitter, 1)

        # ── Confirm / cancel ──────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(self.reject)
        self._import_btn = QPushButton("📥 Import Selected")
        self._import_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        self._import_btn.setFixedWidth(150)
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._import_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    def _browse(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Video Directory",
            self._directory or str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
            | QFileDialog.Option.DontResolveSymlinks
            | QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self._directory = directory
            self._dir_edit.setText(directory)
            self._do_scan()

    def _do_scan(self):
        directory = self._dir_edit.text().strip() or self._directory
        if not directory or not Path(directory).is_dir():
            QMessageBox.warning(self, "Invalid Directory", "Please select a valid directory first.")
            return
        self._directory = directory
        self._scan_result = _scan_video_directory(directory)
        self._populate_table()

    def _populate_table(self):
        self._table.setRowCount(0)
        new_count = exists_count = 0

        for series_name, episodes in sorted(
            self._scan_result.items(), key=lambda kv: kv[0].lower()
        ):
            already = series_name.lower() in self._existing_titles
            if already:
                exists_count += 1
            else:
                new_count += 1

            row = self._table.rowCount()
            self._table.insertRow(row)

            # Col 0 – checkbox (wrapped in a centred container)
            chk = QCheckBox()
            chk.setChecked(not already)
            chk.setStyleSheet("QCheckBox { margin-left:6px; }")
            container = QWidget()
            c_lay = QHBoxLayout(container)
            c_lay.addWidget(chk)
            c_lay.setAlignment(Qt.AlignCenter)
            c_lay.setContentsMargins(0, 0, 0, 0)
            self._table.setCellWidget(row, 0, container)

            # Col 1 – series name (store original as UserRole for retrieval)
            name_item = QTableWidgetItem(series_name)
            name_item.setData(Qt.UserRole, series_name)
            name_item.setToolTip(series_name)
            self._table.setItem(row, 1, name_item)

            # Col 2 – episode count
            ep_item = QTableWidgetItem(str(len(episodes)))
            ep_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 2, ep_item)

            # Col 3 – new / already-exists badge
            if already:
                st_item = QTableWidgetItem("⚠ Already exists")
                st_item.setForeground(QColor("#f39c12"))
            else:
                st_item = QTableWidgetItem("✓ New")
                st_item.setForeground(QColor("#2ecc71"))
            self._table.setItem(row, 3, st_item)

        total = len(self._scan_result)
        self._status_lbl.setText(
            f"Found {total} series — {new_count} new, {exists_count} already in listings."
        )
        self._import_btn.setEnabled(total > 0)

    # ------------------------------------------------------------------
    def _select_all_new(self):
        for row in range(self._table.rowCount()):
            st = self._table.item(row, 3)
            if st and "New" in st.text():
                self._set_row_check(row, True)

    def _deselect_all(self):
        for row in range(self._table.rowCount()):
            self._set_row_check(row, False)

    def _set_row_check(self, row: int, state: bool):
        cw = self._table.cellWidget(row, 0)
        if cw:
            chk = cw.findChild(QCheckBox)
            if chk:
                chk.setChecked(state)

    # ------------------------------------------------------------------
    def get_selected_series(self) -> "list[str]":
        """Return the list of series names whose checkboxes are ticked."""
        selected = []
        for row in range(self._table.rowCount()):
            cw = self._table.cellWidget(row, 0)
            if cw:
                chk = cw.findChild(QCheckBox)
                if chk and chk.isChecked():
                    item = self._table.item(row, 1)
                    if item:
                        selected.append(item.data(Qt.UserRole))
        return selected

    def get_scan_result(self) -> dict:
        return self._scan_result

    def get_metadata(self) -> dict:
        return {
            "type": self._f_type.currentText(),
            "status": self._f_status.currentText(),
            "year": self._f_year.value(),
            "genres": self._f_genres.text().strip(),
            "tags": self._f_tags.text().strip(),
            "creator": self._f_creator.text().strip(),
        }


# -------------------------------------------------------------------
# Sub-tab: Content Listings
# -------------------------------------------------------------------
class ContentListingsSubTab(QWidget):
    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager
        self._entries: List[Dict[str, Any]] = []
        self._selected_id: Optional[str] = None
        self._filter_type = "All"
        self._filter_status = "All"
        self._search_query = ""
        self._advanced_search_criteria = None

        # ---- Root layout ----
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        # ---- Toolbar ----
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title_lbl = QLabel("🎬 Content Listings")
        title_lbl.setStyleSheet("font-size:18px;font-weight:bold;color:#00bcd4;")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search titles…")
        self.search_box.setFixedWidth(200)
        self.search_box.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_box)

        adv_search_btn = QPushButton("🔍 Advanced")
        adv_search_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        adv_search_btn.setFixedWidth(110)
        adv_search_btn.clicked.connect(self._on_advanced_search)
        apply_shadow_effect(adv_search_btn)
        toolbar.addWidget(adv_search_btn)

        self.clear_adv_btn = QPushButton("❌ Clear Advanced")
        self.clear_adv_btn.setStyleSheet(
            "QPushButton { background:#c0392b; color:white; border:none; border-radius:4px; padding:2px 8px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#e74c3c; }"
        )
        self.clear_adv_btn.setFixedWidth(130)
        self.clear_adv_btn.clicked.connect(self._clear_advanced_search)
        self.clear_adv_btn.hide()
        toolbar.addWidget(self.clear_adv_btn)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Types"] + ENTRY_TYPES)
        self.type_combo.currentTextChanged.connect(self._on_type_filter)
        toolbar.addWidget(self.type_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["All Status"] + ENTRY_STATUS)
        self.status_combo.currentTextChanged.connect(self._on_status_filter)
        toolbar.addWidget(self.status_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Sort by: Title",
            "Sort by: Rating",
            "Sort by: Episodes",
            "Sort by: Current Episode",
            "Sort by: Date",
            "Sort by: Type",
            "Sort by: Status",
            "Sort by: Local Filename",
            "Sort by: Tags"
        ])
        self.sort_combo.setFixedWidth(150)
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_combo)

        self.sort_order_combo = QComboBox()
        self.sort_order_combo.addItems(["Ascending", "Descending"])
        self.sort_order_combo.setFixedWidth(100)
        self.sort_order_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_order_combo)

        # ── Pair 1: Add Entry (top) / Import Dir (bottom) ──────────────
        entry_pair = QWidget()
        entry_pair_vbox = QVBoxLayout(entry_pair)
        entry_pair_vbox.setContentsMargins(0, 0, 0, 0)
        entry_pair_vbox.setSpacing(3)

        add_btn = QPushButton("＋ Add Entry")
        add_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        add_btn.setFixedWidth(120)
        add_btn.clicked.connect(self._on_add_new)
        apply_shadow_effect(add_btn)

        import_dir_btn = QPushButton("📂 Import Dir")
        import_dir_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        import_dir_btn.setFixedWidth(120)
        import_dir_btn.setToolTip(
            "Scan a video directory and auto-create listings\n"
            "for series that don't already have an entry."
        )
        import_dir_btn.clicked.connect(self._on_import_from_directory)
        apply_shadow_effect(import_dir_btn)

        entry_pair_vbox.addWidget(add_btn)
        entry_pair_vbox.addWidget(import_dir_btn)
        toolbar.addWidget(entry_pair)

        # ── Pair 2: Sync Backup (top) / Update Backup (bottom) ─────────
        backup_pair = QWidget()
        backup_pair_vbox = QVBoxLayout(backup_pair)
        backup_pair_vbox.setContentsMargins(0, 0, 0, 0)
        backup_pair_vbox.setSpacing(3)

        sync_btn = QPushButton("🔄 Sync Backup")
        sync_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        sync_btn.setFixedWidth(130)
        sync_btn.clicked.connect(self._synchronize_listings)
        apply_shadow_effect(sync_btn)

        update_btn = QPushButton("⚡ Update Backup")
        update_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        update_btn.setFixedWidth(130)
        update_btn.clicked.connect(self._update_encrypted_backup)
        apply_shadow_effect(update_btn)

        backup_pair_vbox.addWidget(sync_btn)
        backup_pair_vbox.addWidget(update_btn)
        toolbar.addWidget(backup_pair)

        root.addLayout(toolbar)

        # ---- Stats bar ----
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color:#888;font-size:11px;")
        root.addWidget(self.stats_label)

        # ---- Splitter: gallery | detail ----
        splitter = QSplitter(Qt.Horizontal)

        # Gallery
        gallery_container = QWidget()
        gallery_vbox = QVBoxLayout(gallery_container)
        gallery_vbox.setContentsMargins(0, 0, 0, 0)
        gallery_vbox.setSpacing(0)

        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setStyleSheet(
            "QScrollArea{border:1px solid #4f545c;border-radius:8px;background:#23272a;}"
        )
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background:#23272a;")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self.gallery_scroll.setWidget(self._grid_widget)
        gallery_vbox.addWidget(self.gallery_scroll)
        splitter.addWidget(gallery_container)

        # Detail panel (wrapped in a scroll area)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setStyleSheet(
            "QScrollArea{border:1px solid #4f545c;border-radius:8px;background:#2c2f33;}"
        )
        self._detail = _DetailPanel()
        self._detail.saved.connect(self._on_entry_saved)
        self._detail.deleted.connect(self._on_entry_deleted)
        detail_scroll.setWidget(self._detail)
        splitter.addWidget(detail_scroll)

        splitter.setSizes([680, 340])
        splitter.setHandleWidth(6)
        root.addWidget(splitter, 1)

        # Context Menu for Gallery background
        self.gallery_scroll.setContextMenuPolicy(Qt.CustomContextMenu)
        self.gallery_scroll.customContextMenuRequested.connect(
            self._show_gallery_context_menu
        )

        # ---- Load data ----
        self._load_data()
        self._rebuild_gallery()
        self._detail.clear_for_new()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_data(self):
        try:
            IMAGE_TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
            if LISTINGS_FILE.exists():
                with open(LISTINGS_FILE, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
        except Exception as e:
            print(f"[ContentListingsSubTab] Failed to load listings: {e}")
            self._entries = []

    def _save_data(self):
        try:
            IMAGE_TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
            with open(LISTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ContentListingsSubTab] Failed to save listings: {e}")

    # ------------------------------------------------------------------
    # Gallery
    # ------------------------------------------------------------------
    def _filtered_entries(self) -> List[Dict[str, Any]]:
        result = self._entries
        if self._filter_type not in ("All", "All Types"):
            result = [e for e in result if e.get("type") == self._filter_type]
        if self._filter_status not in ("All", "All Status"):
            result = [e for e in result if e.get("status") == self._filter_status]

        # Advanced Search Criteria
        if hasattr(self, "_advanced_search_criteria") and self._advanced_search_criteria:
            crit = self._advanced_search_criteria
            inc_ent = set(crit.get("include_entities", []))
            exc_ent = set(crit.get("exclude_entities", []))
            inc_tag = {t.lower() for t in crit.get("include_tags", [])}
            exc_tag = {t.lower() for t in crit.get("exclude_tags", [])}
            inc_genre = {g.lower() for g in crit.get("include_genres", [])}
            exc_genre = {g.lower() for g in crit.get("exclude_genres", [])}
            match_mode = crit.get("match_mode", "AND")

            filtered = []
            for e in result:
                # Get fields
                e_ent = set(e.get("associated_entities", []))
                e_tags = {t.strip().lower() for t in e.get("tags", "").split(",") if t.strip()}
                e_genres = {g.strip().lower() for g in e.get("genres", "").split(",") if g.strip()}

                # Negative filtering (exclusions): if any matches, exclude this entry
                if exc_ent.intersection(e_ent):
                    continue
                if exc_tag.intersection(e_tags):
                    continue
                if exc_genre.intersection(e_genres):
                    continue

                # Positive filtering (inclusions)
                ent_active = len(inc_ent) > 0
                tag_active = len(inc_tag) > 0
                genre_active = len(inc_genre) > 0

                if not ent_active and not tag_active and not genre_active:
                    # No inclusions requested, so it's a match
                    filtered.append(e)
                    continue

                if match_mode == "AND":
                    # Must match all included criteria in active categories
                    ent_ok = not ent_active or inc_ent.issubset(e_ent)
                    tag_ok = not tag_active or inc_tag.issubset(e_tags)
                    genre_ok = not genre_active or inc_genre.issubset(e_genres)

                    if ent_ok and tag_ok and genre_ok:
                        filtered.append(e)
                else:
                    # OR mode: must match at least one of the active inclusions
                    ent_match = ent_active and len(inc_ent.intersection(e_ent)) > 0
                    tag_match = tag_active and len(inc_tag.intersection(e_tags)) > 0
                    genre_match = genre_active and len(inc_genre.intersection(e_genres)) > 0

                    if ent_match or tag_match or genre_match:
                        filtered.append(e)

            result = filtered

        if self._search_query:
            q = self._search_query.lower()
            all_entities = []
            try:
                if ENTITIES_FILE.exists():
                    with open(ENTITIES_FILE, "r", encoding="utf-8") as f:
                        all_entities = json.load(f)
            except Exception:
                pass
            entity_names_map = {ent["id"]: ent["name"].lower() for ent in all_entities}

            filtered = []
            for e in result:
                title = e.get("title", "").lower()
                genres = e.get("genres", "").lower()
                tags = e.get("tags", "").lower()
                creator = e.get("creator", "").lower()

                assoc_match = False
                for ent_id in e.get("associated_entities", []):
                    if ent_id in entity_names_map and q in entity_names_map[ent_id]:
                        assoc_match = True
                        break

                if (
                    q in title
                    or q in genres
                    or q in tags
                    or q in creator
                    or assoc_match
                ):
                    filtered.append(e)
            result = filtered

        # Apply Sort
        sort_field = self.sort_combo.currentText()
        reverse = self.sort_order_combo.currentText() == "Descending"
        
        if sort_field == "Sort by: Title":
            result = sorted(result, key=lambda x: x.get("title", "").lower(), reverse=reverse)
        elif sort_field == "Sort by: Type":
            result = sorted(result, key=lambda x: x.get("type", "").lower(), reverse=reverse)
        elif sort_field == "Sort by: Status":
            result = sorted(result, key=lambda x: x.get("status", "").lower(), reverse=reverse)
        elif sort_field == "Sort by: Rating":
            result = sorted(result, key=lambda x: x.get("rating", 0), reverse=reverse)
        elif sort_field == "Sort by: Episodes":
            result = sorted(result, key=lambda x: x.get("episodes", 0), reverse=reverse)
        elif sort_field == "Sort by: Current Episode":
            result = sorted(result, key=lambda x: x.get("current_episode", 0), reverse=reverse)
        elif sort_field == "Sort by: Date":
            result = sorted(result, key=lambda x: x.get("date_watched", ""), reverse=reverse)
        elif sort_field == "Sort by: Local Filename":
            result = sorted(result, key=lambda x: Path(x.get("local_file", "")).name.lower() if x.get("local_file") else "", reverse=reverse)
        elif sort_field == "Sort by: Tags":
            result = sorted(result, key=lambda x: x.get("tags", "").lower(), reverse=reverse)

        return result

    def _rebuild_gallery(self):
        # Clear old widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        visible = self._filtered_entries()

        if not visible:
            placeholder = QLabel(
                "No entries found.\nClick '＋ Add Entry' to get started."
            )
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color:#555;font-size:14px;")
            self._grid.addWidget(placeholder, 0, 0)
        else:
            cols = max(1, self.gallery_scroll.width() // (CARD_SIZE + 20))
            for i, entry in enumerate(visible):
                card = _ListingCard(entry)
                card.clicked.connect(self._on_card_clicked)
                card.add_requested.connect(self._on_add_new)
                card.delete_requested.connect(self._on_card_delete_requested)
                card.image_remove_requested.connect(
                    self._on_card_image_remove_requested
                )
                self._grid.addWidget(card, i // cols, i % cols)

        # Stats
        total = len(self._entries)
        completed = sum(1 for e in self._entries if e.get("status") == "Completed")
        self.stats_label.setText(
            f"{total} entries total · {completed} completed · showing {len(visible)}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_gallery()

    def showEvent(self, event):
        super().showEvent(event)
        self._rebuild_gallery()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_advanced_search(self):
        # Load entities dynamically
        all_entities = []
        try:
            if ENTITIES_FILE.exists():
                with open(ENTITIES_FILE, "r", encoding="utf-8") as f:
                    all_entities = json.load(f)
        except Exception:
            pass

        dialog = AdvancedSearchDialog(self, entries=self._entries, entities=all_entities)
        if self._advanced_search_criteria:
            dialog.load_criteria(self._advanced_search_criteria)

        if dialog.exec():
            criteria = dialog.get_criteria()
            
            # Check if any criteria is set
            has_crit = any(criteria[k] for k in criteria if k != "match_mode")
            if has_crit:
                self._advanced_search_criteria = criteria
                self.clear_adv_btn.show()
            else:
                self._advanced_search_criteria = None
                self.clear_adv_btn.hide()
                
            self._rebuild_gallery()

    def _clear_advanced_search(self):
        self._advanced_search_criteria = None
        self.clear_adv_btn.hide()
        self._rebuild_gallery()

    @Slot(str)
    def _on_card_clicked(self, entry_id: str):
        self._selected_id = entry_id
        entry = next((e for e in self._entries if e["id"] == entry_id), None)
        if entry:
            self._detail.load_entry(entry)

    def _on_card_delete_requested(self, entry_id: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entry from your listings?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._on_entry_deleted(entry_id)

    def _on_card_image_remove_requested(self, entry_id: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete Image",
            "Are you sure you want to permanently delete the image for this listing?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            entry = next((e for e in self._entries if e["id"] == entry_id), None)
            if entry:
                img_path = entry.get("image_path", "")
                if img_path:
                    try:
                        p = Path(img_path)
                        if p.exists() and p.is_file():
                            p.unlink(missing_ok=True)
                    except Exception as e:
                        print(f"Failed to delete physical image file: {e}")
                entry["image_path"] = ""
                self._save_data()
                self._rebuild_gallery()
                if self._selected_id == entry_id:
                    self._detail.load_entry(entry)

    def _show_gallery_context_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )
        add_act = QAction("＋ Add New Content", self)
        add_act.triggered.connect(self._on_add_new)
        menu.addAction(add_act)
        menu.exec(self.gallery_scroll.mapToGlobal(pos))

    @Slot()
    def _on_add_new(self):
        self._selected_id = None
        self._detail.clear_for_new()

    @Slot(dict)
    def _on_entry_saved(self, entry: Dict[str, Any]):
        idx = next(
            (i for i, e in enumerate(self._entries) if e["id"] == entry["id"]), None
        )
        if idx is not None:
            self._entries[idx] = entry
        else:
            self._entries.insert(0, entry)
        self._save_data()
        self._rebuild_gallery()
        self._detail.load_entry(entry)

    @Slot(str)
    def _on_entry_deleted(self, entry_id: str):
        self._entries = [e for e in self._entries if e["id"] != entry_id]
        self._save_data()
        self._rebuild_gallery()
        self._detail.clear_for_new()

    @Slot(str)
    def _on_search(self, text: str):
        self._search_query = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_type_filter(self, text: str):
        self._filter_type = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_status_filter(self, text: str):
        self._filter_status = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_sort_changed(self, text: str):
        self._rebuild_gallery()

    @Slot()
    def _synchronize_listings(self):
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to sync.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / "listings.json.enc")

        if not os.path.exists(enc_file_path):
            QMessageBox.warning(
                self,
                "Backup Not Found",
                "No encrypted listings backup file found to synchronize from. Use 'Update Backup' first to generate it.",
            )
            return

        try:
            SecureJsonVault = self.vault_manager.SecureJsonVault
            secret_key = self.vault_manager.secret_key

            # 1. Load and decrypt remote entries
            temp_vault = SecureJsonVault(secret_key, enc_file_path)
            java_str = temp_vault.loadData()
            remote_json_str = str(java_str)
            try:
                remote_entries = json.loads(remote_json_str)
            except Exception:
                remote_entries = []

            # 2. Merge local and remote entries by unique ID
            local_entries = self._entries
            merged_dict = {
                item["id"]: item
                for item in remote_entries
                if isinstance(item, dict) and "id" in item
            }
            for item in local_entries:
                if isinstance(item, dict) and "id" in item:
                    merged_dict[item["id"]] = item

            merged_entries = list(merged_dict.values())

            # 3. Save merged entries locally
            self._entries = merged_entries
            self._save_data()
            self._rebuild_gallery()

            QMessageBox.information(
                self,
                "Synchronization Complete",
                f"Successfully synchronized listings!\nMerged local and backup entries to a total of {len(merged_entries)} entries.",
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Sync Error", f"An error occurred during synchronization:\n{e}"
            )

    @Slot()
    def _update_encrypted_backup(self):
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to update backup.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / "listings.json.enc")

        try:
            SecureJsonVault = self.vault_manager.SecureJsonVault
            secret_key = self.vault_manager.secret_key

            temp_vault = SecureJsonVault(secret_key, enc_file_path)
            json_content = json.dumps(self._entries, indent=2, ensure_ascii=False)
            temp_vault.saveData(json_content)

            QMessageBox.information(
                self,
                "Backup Updated",
                f"Successfully generated encrypted backup listings file with {len(self._entries)} entries.",
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Backup Error", f"An error occurred while generating backup:\n{e}"
            )

    # ------------------------------------------------------------------
    @Slot()
    def _on_import_from_directory(self):
        """Open the directory-import wizard and create listings for new series."""
        existing_titles = {e.get("title", "").lower() for e in self._entries}
        dlg = _DirectoryImportDialog(existing_titles, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        selected_series = dlg.get_selected_series()
        if not selected_series:
            QMessageBox.information(
                self, "Nothing to Import",
                "No series were selected. Nothing was imported."
            )
            return

        scan_result = dlg.get_scan_result()
        meta = dlg.get_metadata()
        today = str(date.today())
        created = 0

        for series_name in selected_series:
            episodes = scan_result.get(series_name, [])
            if not episodes:
                continue

            # Build the per-episode sub-list
            episode_list = []
            for idx, (ep_num, file_path) in enumerate(episodes):
                episode_list.append({
                    "id": str(uuid.uuid4()),
                    "number": ep_num if ep_num is not None else (idx + 1),
                    "title": "",
                    "date_watched": today,
                    "rating": 0,
                    "review": "",
                    "image_path": "",
                    "local_file": file_path,
                    "web_link": "",
                })

            entry = {
                "id": str(uuid.uuid4()),
                "title": series_name,
                "type": meta["type"],
                "status": meta["status"],
                "rating": 0,
                "year": meta["year"],
                "episodes": len(episodes),
                "current_episode": 0,
                "genres": meta["genres"],
                "tags": meta["tags"],
                "creator": meta.get("creator", ""),
                "associated_entities": [],
                # First episode's file is the series-level local file
                "local_file": episodes[0][1],
                "web_link": "",
                "review": "",
                "image_path": "",
                "episode_list": episode_list,
                "date_added": today,
            }
            self._entries.insert(0, entry)
            created += 1

        if created:
            self._save_data()
            self._rebuild_gallery()
            QMessageBox.information(
                self,
                "Import Complete",
                f"Successfully imported {created} new listing"
                f"{'s' if created != 1 else ''}.",
            )
        else:
            QMessageBox.information(
                self, "No New Entries",
                "All selected series already had listings — nothing was added."
            )


# -------------------------------------------------------------------
# Sub-tab: Entity Listings
# -------------------------------------------------------------------
class EntityListingsSubTab(QWidget):
    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager
        self._entities: List[Dict[str, Any]] = []
        self._selected_id: Optional[str] = None
        self._filter_type = "All"
        self._filter_role = "All"
        self._search_query = ""

        # ---- Root layout ----
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        # ---- Toolbar ----
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title_lbl = QLabel("👥 Entity Listings")
        title_lbl.setStyleSheet("font-size:18px;font-weight:bold;color:#00bcd4;")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search entities…")
        self.search_box.setFixedWidth(200)
        self.search_box.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_box)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Types"] + ENTITY_TYPES)
        self.type_combo.currentTextChanged.connect(self._on_type_filter)
        toolbar.addWidget(self.type_combo)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["All Roles"] + ENTITY_ROLES)
        self.role_combo.currentTextChanged.connect(self._on_role_filter)
        toolbar.addWidget(self.role_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Sort by: Name",
            "Sort by: Rating",
            "Sort by: Type",
            "Sort by: Role",
            "Sort by: Date Added",
            "Sort by: Credits Count"
        ])
        self.sort_combo.setFixedWidth(150)
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_combo)

        self.sort_order_combo = QComboBox()
        self.sort_order_combo.addItems(["Ascending", "Descending"])
        self.sort_order_combo.setFixedWidth(100)
        self.sort_order_combo.currentTextChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_order_combo)

        add_btn = QPushButton("＋ Add Entity")
        add_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        add_btn.setFixedWidth(120)
        add_btn.clicked.connect(self._on_add_new)
        apply_shadow_effect(add_btn)
        toolbar.addWidget(add_btn)

        sync_btn = QPushButton("🔄 Sync Backup")
        sync_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        sync_btn.setFixedWidth(120)
        sync_btn.clicked.connect(self._synchronize_listings)
        apply_shadow_effect(sync_btn)
        toolbar.addWidget(sync_btn)

        update_btn = QPushButton("⚡ Update Backup")
        update_btn.setStyleSheet(SHARED_BUTTON_STYLE)
        update_btn.setFixedWidth(130)
        update_btn.clicked.connect(self._update_encrypted_backup)
        apply_shadow_effect(update_btn)
        toolbar.addWidget(update_btn)

        root.addLayout(toolbar)

        # ---- Stats bar ----
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color:#888;font-size:11px;")
        root.addWidget(self.stats_label)

        # ---- Splitter: gallery | detail ----
        splitter = QSplitter(Qt.Horizontal)

        # Gallery
        gallery_container = QWidget()
        gallery_vbox = QVBoxLayout(gallery_container)
        gallery_vbox.setContentsMargins(0, 0, 0, 0)
        gallery_vbox.setSpacing(0)

        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setStyleSheet(
            "QScrollArea{border:1px solid #4f545c;border-radius:8px;background:#23272a;}"
        )
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background:#23272a;")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self.gallery_scroll.setWidget(self._grid_widget)
        gallery_vbox.addWidget(self.gallery_scroll)
        splitter.addWidget(gallery_container)

        # Detail panel (wrapped in a scroll area)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setStyleSheet(
            "QScrollArea{border:1px solid #4f545c;border-radius:8px;background:#2c2f33;}"
        )
        self._detail = _EntityDetailPanel()
        self._detail.saved.connect(self._on_entity_saved)
        self._detail.deleted.connect(self._on_entity_deleted)
        detail_scroll.setWidget(self._detail)
        splitter.addWidget(detail_scroll)

        splitter.setSizes([680, 340])
        splitter.setHandleWidth(6)
        root.addWidget(splitter, 1)

        # Context Menu for Gallery background
        self.gallery_scroll.setContextMenuPolicy(Qt.CustomContextMenu)
        self.gallery_scroll.customContextMenuRequested.connect(
            self._show_gallery_context_menu
        )

        # ---- Load data ----
        self._load_data()
        self._rebuild_gallery()
        self._detail.clear_for_new()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_data(self):
        try:
            IMAGE_TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
            if ENTITIES_FILE.exists():
                with open(ENTITIES_FILE, "r", encoding="utf-8") as f:
                    self._entities = json.load(f)
        except Exception as e:
            print(f"[EntityListingsSubTab] Failed to load entities: {e}")
            self._entities = []

    def _save_data(self):
        try:
            IMAGE_TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
            with open(ENTITIES_FILE, "w", encoding="utf-8") as f:
                json.dump(self._entities, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[EntityListingsSubTab] Failed to save entities: {e}")

    # ------------------------------------------------------------------
    # Gallery
    # ------------------------------------------------------------------
    def _filtered_entities(self) -> List[Dict[str, Any]]:
        result = self._entities
        if self._filter_type not in ("All", "All Types"):
            result = [e for e in result if e.get("type") == self._filter_type]
        if self._filter_role not in ("All", "All Roles"):
            result = [e for e in result if e.get("role") == self._filter_role]
        if self._search_query:
            q = self._search_query.lower()
            result = [
                e
                for e in result
                if q in e.get("name", "").lower()
                or q in e.get("associated_content", "").lower()
                or q in e.get("notes", "").lower()
            ]

        # Sorting logic
        sort_text = self.sort_combo.currentText()
        is_descending = self.sort_order_combo.currentText() == "Descending"

        def get_sort_key(entity):
            if "Name" in sort_text:
                return (entity.get("name") or "").lower()
            elif "Rating" in sort_text:
                return entity.get("rating") or 0
            elif "Type" in sort_text:
                return (entity.get("type") or "").lower()
            elif "Role" in sort_text:
                return (entity.get("role") or "").lower()
            elif "Date Added" in sort_text:
                return entity.get("date_added") or ""
            elif "Credits Count" in sort_text:
                return len(entity.get("credit_list") or [])
            return (entity.get("name") or "").lower()

        result = sorted(result, key=get_sort_key, reverse=is_descending)
        return result

    def _rebuild_gallery(self):
        # Clear old widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        visible = self._filtered_entities()

        if not visible:
            placeholder = QLabel(
                "No entities found.\nClick '＋ Add Entity' to get started."
            )
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color:#555;font-size:14px;")
            self._grid.addWidget(placeholder, 0, 0)
        else:
            cols = max(1, self.gallery_scroll.width() // (CARD_SIZE + 20))
            for i, entity in enumerate(visible):
                card = _EntityCard(entity)
                card.clicked.connect(self._on_card_clicked)
                card.add_requested.connect(self._on_add_new)
                card.delete_requested.connect(self._on_card_delete_requested)
                self._grid.addWidget(card, i // cols, i % cols)

        # Stats
        total = len(self._entities)
        completed = sum(1 for e in self._entities if e.get("rating", 0) >= 8)
        self.stats_label.setText(
            f"{total} entities total · {completed} highly rated (>=8) · showing {len(visible)}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_gallery()

    def showEvent(self, event):
        super().showEvent(event)
        self._rebuild_gallery()

    def _on_sort_changed(self, text):
        self._rebuild_gallery()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    @Slot(str)
    def _on_card_clicked(self, entity_id: str):
        self._selected_id = entity_id
        entity = next((e for e in self._entities if e["id"] == entity_id), None)
        if entity:
            self._detail.load_entity(entity)

    def _on_card_delete_requested(self, entity_id: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entity from your listings?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._on_entity_deleted(entity_id)

    def _show_gallery_context_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )
        add_act = QAction("＋ Add New Entity", self)
        add_act.triggered.connect(self._on_add_new)
        menu.addAction(add_act)
        menu.exec(self.gallery_scroll.mapToGlobal(pos))

    @Slot()
    def _on_add_new(self):
        self._selected_id = None
        self._detail.clear_for_new()

    @Slot(dict)
    def _on_entity_saved(self, entity: Dict[str, Any]):
        idx = next(
            (i for i, e in enumerate(self._entities) if e["id"] == entity["id"]), None
        )
        if idx is not None:
            self._entities[idx] = entity
        else:
            self._entities.insert(0, entity)
        self._save_data()
        self._rebuild_gallery()
        self._detail.load_entity(entity)

    @Slot(str)
    def _on_entity_deleted(self, entity_id: str):
        self._entities = [e for e in self._entities if e["id"] != entity_id]
        self._save_data()
        self._rebuild_gallery()
        self._detail.clear_for_new()

    @Slot(str)
    def _on_search(self, text: str):
        self._search_query = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_type_filter(self, text: str):
        self._filter_type = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_role_filter(self, text: str):
        self._filter_role = text
        self._rebuild_gallery()

    @Slot()
    def _synchronize_listings(self):
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to sync.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / "entities.json.enc")

        if not os.path.exists(enc_file_path):
            QMessageBox.warning(
                self,
                "Backup Not Found",
                "No encrypted entities backup file found to synchronize from. Use 'Update Backup' first to generate it.",
            )
            return

        try:
            SecureJsonVault = self.vault_manager.SecureJsonVault
            secret_key = self.vault_manager.secret_key

            # 1. Load and decrypt remote entries
            temp_vault = SecureJsonVault(secret_key, enc_file_path)
            java_str = temp_vault.loadData()
            remote_json_str = str(java_str)
            try:
                remote_entries = json.loads(remote_json_str)
            except Exception:
                remote_entries = []

            # 2. Merge local and remote entries by unique ID
            local_entries = self._entities
            merged_dict = {
                item["id"]: item
                for item in remote_entries
                if isinstance(item, dict) and "id" in item
            }
            for item in local_entries:
                if isinstance(item, dict) and "id" in item:
                    merged_dict[item["id"]] = item

            merged_entries = list(merged_dict.values())

            # 3. Save merged entries locally
            self._entities = merged_entries
            self._save_data()
            self._rebuild_gallery()

            QMessageBox.information(
                self,
                "Synchronization Complete",
                f"Successfully synchronized entities!\nMerged local and backup entries to a total of {len(merged_entries)} entries.",
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Sync Error", f"An error occurred during synchronization:\n{e}"
            )

    @Slot()
    def _update_encrypted_backup(self):
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to update backup.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / "entities.json.enc")

        try:
            SecureJsonVault = self.vault_manager.SecureJsonVault
            secret_key = self.vault_manager.secret_key

            temp_vault = SecureJsonVault(secret_key, enc_file_path)
            json_content = json.dumps(self._entities, indent=2, ensure_ascii=False)
            temp_vault.saveData(json_content)

            QMessageBox.information(
                self,
                "Backup Updated",
                f"Successfully generated encrypted backup entities file with {len(self._entities)} entries.",
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Backup Error", f"An error occurred while generating backup:\n{e}"
            )


# -------------------------------------------------------------------
# Main tab: Listings Tab containing the split sub-tabs
# -------------------------------------------------------------------
class ListingsTab(QWidget):
    """Media tracking and entity listing tab."""

    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager

        # ---- Root layout ----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab Widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(
            "QTabWidget::pane { border: none; background: #2c2f33; }"
            "QTabBar::tab { background: #23272a; color: #888; padding: 10px 20px; font-weight: bold; border-top-left-radius: 6px; border-top-right-radius: 6px; }"
            "QTabBar::tab:selected { background: #2c2f33; color: #00bcd4; border-bottom: 2px solid #00bcd4; }"
        )

        self.content_listings = ContentListingsSubTab(vault_manager=vault_manager)
        self.entity_listings = EntityListingsSubTab(vault_manager=vault_manager)

        self.tab_widget.addTab(self.content_listings, "🎬 Content Listings")
        self.tab_widget.addTab(self.entity_listings, "👥 Entity Listings")
        layout.addWidget(self.tab_widget)


class ThumbnailSelectionDialog(QDialog):
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Representative Thumbnail")
        self.setMinimumSize(500, 600)
        self.file_path = file_path
        self.selected_image = None

        self.p = Path(file_path)
        self.suffix = self.p.suffix.lower()

        self.cap = None
        self.pdf_doc = None
        self.total_frames = 0
        self.fps = 24.0

        # Debounce timer + current worker for async frame extraction
        self._frame_timer = QTimer(self)
        self._frame_timer.setSingleShot(True)
        self._frame_timer.setInterval(180)  # ms idle before firing
        self._frame_timer.timeout.connect(self._start_frame_worker)
        self._frame_worker: Optional[_FrameWorker] = None

        self._init_ui()
        self._load_file()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #2c2f33;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #7289da;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #677bc4;
            }
            QSlider::groove:horizontal {
                border: 1px solid #4f545c;
                height: 8px;
                background: #1a1c1e;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #00bcd4;
                border: 1px solid #0097a7;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSpinBox {
                background-color: #1a1c1e;
                color: white;
                border: 1px solid #4f545c;
                border-radius: 4px;
                padding: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.info_lbl = QLabel(f"File: {self.p.name}")
        self.info_lbl.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #00bcd4;"
        )
        layout.addWidget(self.info_lbl)

        self.preview_lbl = QLabel("Loading preview...")
        self.preview_lbl.setAlignment(Qt.AlignCenter)
        self.preview_lbl.setMinimumSize(400, 400)
        self.preview_lbl.setStyleSheet(
            "background-color: #1a1c1e; border: 2px solid #4f545c; border-radius: 8px;"
        )
        layout.addWidget(self.preview_lbl, 1)

        self.controls_layout = QHBoxLayout()
        layout.addLayout(self.controls_layout)

        btns_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("background-color: #4f545c;")
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Select Frame / Page")
        self.save_btn.clicked.connect(self.accept)

        btns_layout.addStretch()
        btns_layout.addWidget(self.cancel_btn)
        btns_layout.addWidget(self.save_btn)
        layout.addLayout(btns_layout)

    def _load_file(self):
        if self.suffix == ".pdf":
            try:
                from PySide6.QtPdf import QPdfDocument

                self.pdf_doc = QPdfDocument()
                if (
                    self.pdf_doc.load(str(self.p.absolute()))
                    == QPdfDocument.Status.Ready
                ):
                    page_count = self.pdf_doc.pageCount()

                    self.page_spin = QSpinBox()
                    self.page_spin.setRange(1, page_count)
                    self.page_spin.setValue(1)
                    self.page_spin.valueChanged.connect(self._update_pdf_preview)

                    self.controls_layout.addWidget(QLabel("Page:"))
                    self.controls_layout.addWidget(self.page_spin)
                    self.controls_layout.addWidget(QLabel(f"of {page_count}"))
                    self.controls_layout.addStretch()

                    self._update_pdf_preview()
                else:
                    self.preview_lbl.setText("Failed to load PDF.")
            except Exception as e:
                self.preview_lbl.setText(f"Error loading PDF: {e}")

        elif self.suffix in (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".m4v"):
            try:
                import cv2

                # Use OpenCV only to probe metadata (no actual decoding)
                try:
                    probe = cv2.VideoCapture(
                        str(self.p.absolute()),
                        cv2.CAP_FFMPEG,
                        [cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_NONE],
                    )
                except Exception:
                    probe = cv2.VideoCapture(str(self.p.absolute()))

                if probe.isOpened():
                    self.total_frames = int(probe.get(cv2.CAP_PROP_FRAME_COUNT)) or 1000
                    self.fps = probe.get(cv2.CAP_PROP_FPS) or 24.0
                    probe.release()

                    self.slider = QSlider(Qt.Horizontal)
                    self.slider.setRange(0, self.total_frames - 1)
                    start_frame = min(
                        max(1, self.total_frames // 10), self.total_frames - 1
                    )
                    self.slider.setValue(start_frame)
                    # Debounce: slider movement restarts the timer instead of
                    # calling the (slow) extraction synchronously each tick
                    self.slider.valueChanged.connect(self._schedule_video_preview)

                    self.frame_spin = QSpinBox()
                    self.frame_spin.setRange(0, self.total_frames - 1)
                    self.frame_spin.setValue(start_frame)
                    self.frame_spin.valueChanged.connect(self.slider.setValue)
                    self.slider.valueChanged.connect(self.frame_spin.setValue)

                    self.controls_layout.addWidget(QLabel("Frame:"))
                    self.controls_layout.addWidget(self.slider, 1)
                    self.controls_layout.addWidget(self.frame_spin)

                    # Kick off the first frame immediately (no debounce needed)
                    self._start_frame_worker()
                else:
                    self.preview_lbl.setText("Failed to open Video.")
            except Exception as e:
                self.preview_lbl.setText(f"Error opening Video: {e}")
        else:
            self.preview_lbl.setText("Unsupported format.")
            self.save_btn.setEnabled(False)

    def _update_pdf_preview(self):
        if not self.pdf_doc:
            return
        page_index = self.page_spin.value() - 1
        qimg = self.pdf_doc.render(page_index, QSize(400, 500))
        if not qimg.isNull():
            self.selected_image = qimg
            px = QPixmap.fromImage(qimg).scaled(
                380, 380, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.preview_lbl.setPixmap(px)

    def _schedule_video_preview(self):
        """Called on every slider tick — just restarts the debounce timer."""
        self._frame_timer.start()

    def _clear_worker(self, worker):
        if self._frame_worker is worker:
            self._frame_worker = None

    def _start_frame_worker(self):
        """Fired by the debounce timer; cancels any in-flight worker and starts a new one."""
        # Cancel previous extraction if still running
        if self._frame_worker is not None:
            try:
                if self._frame_worker.isRunning():
                    self._frame_worker.cancel()
                    self._frame_worker.signals.frame_ready.disconnect()
                    self._frame_worker.signals.failed.disconnect()
            except RuntimeError:
                pass
            self._frame_worker = None

        frame_idx = self.slider.value()
        self.preview_lbl.setText("Loading…")

        worker = _FrameWorker(
            str(self.p.absolute()), frame_idx, self.total_frames, self.fps
        )
        worker.signals.frame_ready.connect(self._on_frame_ready)
        worker.signals.failed.connect(self._on_frame_failed)
        # Clear local reference when finished, then clean up the C++ object
        worker.finished.connect(lambda: self._clear_worker(worker))
        worker.finished.connect(worker.deleteLater)
        self._frame_worker = worker
        worker.start()

    def _on_frame_ready(self, frame):
        """Slot called from worker signal (marshalled to main thread by Qt)."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
        self.selected_image = qimg
        px = QPixmap.fromImage(qimg).scaled(
            380, 380, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.preview_lbl.setPixmap(px)

    def _on_frame_failed(self):
        self.preview_lbl.setText("Failed to decode frame from video.")

    def closeEvent(self, event):
        # Stop debounce timer and cancel any running worker cleanly
        self._frame_timer.stop()
        if self._frame_worker is not None:
            try:
                if self._frame_worker.isRunning():
                    self._frame_worker.cancel()
                    self._frame_worker.wait(500)  # give it up to 500 ms to exit
            except RuntimeError:
                pass
        if self.cap:
            self.cap.release()
        super().closeEvent(event)
