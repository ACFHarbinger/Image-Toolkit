import json
import zipfile
import re
import subprocess
import platform
import cv2
import shutil

from pathlib import Path
from datetime import date
from typing import List, Dict, Any
from PySide6.QtPdf import QPdfDocument
from PySide6.QtCore import (
    Qt,
    Signal,
    Slot,
    QSettings,
    QUrl,
    QSize,
    QThread,
    QObject,
    QRunnable,
)
from PySide6.QtGui import QDesktopServices, QImage
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDialog,
    QListWidget,
    QListWidgetItem,
)

import base
import backend.src.constants as udef
from backend.src.core.vault_manager import VaultManager  # noqa: F401
from ....styles.style import SHARED_BUTTON_STYLE
from ....utils.lru_image_cache import LRUImageCache
from ....components.frame_selection_dialog import (
    extract_video_frame_via_ffmpeg,
)
from ....constants.listings import (
    LISTINGS_FILE,  # noqa: F401
    ENTITIES_FILE,  # noqa: F401
    LISTING_IMAGES_DIR,
    VIDEO_IMPORT_EXTS,
)


# ---------------------------------------------------------------------------

# Async thumbnail infrastructure for listing/entity cards
# ---------------------------------------------------------------------------

# Shared LRU cache: stores scaled QImages keyed by absolute path.
# 250 entries ≈ ~30 MB at 130×130 RGBA — well within budget.
_CARD_THUMB_CACHE: LRUImageCache = LRUImageCache(maxsize=250)


class _ThumbWorkerSignals(QObject):
    ready = Signal(str, QImage)  # (absolute_path, scaled QImage)


class _ThumbWorker(QRunnable):
    """Load and scale a card thumbnail off the main thread."""

    def __init__(self, path: str, size: int):
        super().__init__()
        self.setAutoDelete(True)
        self._path = path
        self._size = size
        self.signals = _ThumbWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            img = QImage(self._path)
            if img.isNull():
                return
            img = img.scaled(
                self._size,
                self._size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            _CARD_THUMB_CACHE[self._path] = img
            self.signals.ready.emit(self._path, img)
        except Exception:
            pass


def save_content_entry_to_db(
    db_path: str, password: str, salt: str, entry: Dict[str, Any]
):
    meta = entry.copy()
    meta.pop("id", None)
    meta.pop("type", None)
    meta.pop("title", None)
    meta.pop("date_added", None)

    # Generate default embedding based on title
    embedding = [0.0] * 1024
    title = entry.get("title", "")
    for i, byte in enumerate(title.encode("utf-8", errors="ignore")):
        if i < 1024:
            embedding[i] = byte / 255.0

    base.insert_listing_secure(
        db_path,
        password,
        salt,
        entry["id"],
        entry.get("type", "Other"),
        entry.get("title", ""),
        json.dumps(meta, ensure_ascii=False),
        entry.get("date_added", str(date.today())),
        embedding,
    )


def save_entity_entry_to_db(
    db_path: str, password: str, salt: str, entity: Dict[str, Any]
):
    meta = entity.copy()
    meta.pop("id", None)
    meta.pop("name", None)
    meta.pop("date_added", None)

    # Generate default embedding based on name
    embedding = [0.0] * 1024
    name = entity.get("name", "")
    for i, byte in enumerate(name.encode("utf-8", errors="ignore")):
        if i < 1024:
            embedding[i] = byte / 255.0

    base.insert_listing_secure(
        db_path,
        password,
        salt,
        entity["id"],
        "Entity",
        entity.get("name", ""),
        json.dumps(meta, ensure_ascii=False),
        entity.get("date_added", str(date.today())),
        embedding,
    )


def _backup_referenced_images(prefix: str, data_list: List[Dict[str, Any]]):
    """Create multi-part ZIP archive of referenced images in assets/migrations."""
    referenced_files = set()

    for entry in data_list:
        img = entry.get("image_path")
        if img:
            referenced_files.add(Path(img).name)
        # Also check episode_list/credit_list
        for sub in entry.get("episode_list", []) + entry.get("credit_list", []):
            sub_img = sub.get("image_path")
            if sub_img:
                referenced_files.add(Path(sub_img).name)

    if not referenced_files:
        return 0

    files_to_backup = []
    for filename in referenced_files:
        p = LISTING_IMAGES_DIR / filename
        if p.exists() and p.is_file():
            files_to_backup.append(p)

    if not files_to_backup:
        return 0

    migrations_dir = Path(udef.ROOT_DIR) / "assets" / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)

    # Clean up old parts
    for old_part in migrations_dir.glob(f"{prefix}.part*.zip"):
        old_part.unlink()

    part_idx = 1
    max_size_bytes = 100 * 1024 * 1024
    current_zip_path = migrations_dir / f"{prefix}.part{part_idx}.zip"
    zf = zipfile.ZipFile(current_zip_path, "w", zipfile.ZIP_DEFLATED)

    try:
        for file_path in files_to_backup:
            if zf.fp.tell() + file_path.stat().st_size > max_size_bytes and zf.filelist:
                zf.close()
                part_idx += 1
                current_zip_path = migrations_dir / f"{prefix}.part{part_idx}.zip"
                zf = zipfile.ZipFile(current_zip_path, "w", zipfile.ZIP_DEFLATED)
            zf.write(file_path, file_path.name)
    finally:
        zf.close()

    return len(files_to_backup)


def _sync_images_from_backup(prefix: str):
    """Load images from ZIP parts in assets/migrations if missing locally."""
    migrations_dir = Path(udef.ROOT_DIR) / "assets" / "migrations"
    if not migrations_dir.exists():
        return 0

    extracted_count = 0
    LISTING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    zip_parts = sorted(migrations_dir.glob(f"{prefix}.part*.zip"))
    for zip_part in zip_parts:
        try:
            with zipfile.ZipFile(zip_part, "r") as zf:
                for member in zf.namelist():
                    target_path = LISTING_IMAGES_DIR / member
                    if not target_path.exists():
                        zf.extract(member, LISTING_IMAGES_DIR)
                        extracted_count += 1
        except Exception as e:
            print(f"Error reading {zip_part}: {e}")

    return extracted_count


def open_file_location(path: str):
    if not path:
        return

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


def _persist_splitter(splitter, key: str) -> None:
    """Wire a QSplitter to QSettings so its position survives restarts (GUI/UX §2.20A)."""
    settings = QSettings("ImageToolkit", "ImageToolkit")
    state = settings.value(f"splitter/{key}")
    if state:
        splitter.restoreState(state)

    splitter.splitterMoved.connect(
        lambda: QSettings("ImageToolkit", "ImageToolkit").setValue(
            f"splitter/{key}", splitter.saveState()
        )
    )


def generate_thumbnail_from_file(file_path: str, dest_path: str) -> bool:
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


def _parse_video_series(filename: str):
    """
    Parse '<Series Name> - <EP_NUM> <suffix>.<ext>' into (series_name, ep_num_or_None).
    Falls back to (stem, None) for filenames that don't contain ' - '.
    """
    stem = Path(filename).stem
    parts = stem.split(" - ", 1)
    if len(parts) < 2:
        return stem.strip(), None
    series_name = parts[0].strip()
    ep_part = parts[1].strip()
    m = re.match(r"^(\d+)", ep_part)
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
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"background:{color}; color:white; font-size:9px; font-weight:bold;"
        f"border-radius:4px; padding:1px 5px;"
    )
    return lbl


# -------------------------------------------------------------------
# Episode Dialog (Content Listings)
# -------------------------------------------------------------------


class _AssociatedEntitiesDialog(QDialog):
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
            item.setData(Qt.ItemDataRole.UserRole, ent["id"])

            # Checkbox state
            if ent["id"] in self.selected_ids:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

            self.list_widget.addItem(item)

    def _filter_list(self):
        # We need to save the check state of currently visible items before repopulating
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            ent_id = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.selected_ids.add(ent_id)
            else:
                self.selected_ids.discard(ent_id)

        self._populate_list()

    def get_selected_ids(self) -> List[str]:
        # Sync the final visible state
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            ent_id = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.selected_ids.add(ent_id)
            else:
                self.selected_ids.discard(ent_id)
        return list(self.selected_ids)


class _AssociatedContentDialog(QDialog):
    """Multi-select dialog for linking content listings to an entity."""

    def __init__(
        self, all_entries: List[Dict[str, Any]], selected_ids: List[str], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Select Associated Content")
        self.setMinimumSize(420, 460)
        self.setStyleSheet("background:#2c2f33; color:white;")

        self.all_entries = all_entries
        self.selected_ids = set(selected_ids)

        layout = QVBoxLayout(self)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Search by title or type…")
        self.search_box.textChanged.connect(self._filter_list)
        layout.addWidget(self.search_box)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { background:#23272a; border:1px solid #4f545c; border-radius:6px; padding:4px; }"
            "QListWidget::item { color:white; padding:4px; border-bottom:1px solid #2c2f33; }"
            "QListWidget::item:hover { background:#00bcd4; color:black; }"
        )
        layout.addWidget(self.list_widget)
        self._populate_list()

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
        for entry in self.all_entries:
            title = entry.get("title", "Untitled")
            etype = entry.get("type", "")
            if query and query not in title.lower() and query not in etype.lower():
                continue
            label = f"{title} ({etype})" if etype else title
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            item.setCheckState(
                Qt.CheckState.Checked
                if entry["id"] in self.selected_ids
                else Qt.CheckState.Unchecked
            )
            self.list_widget.addItem(item)

    def _filter_list(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            eid = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.selected_ids.add(eid)
            else:
                self.selected_ids.discard(eid)
        self._populate_list()

    def get_selected_ids(self) -> List[str]:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            eid = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.selected_ids.add(eid)
            else:
                self.selected_ids.discard(eid)
        return list(self.selected_ids)


# -------------------------------------------------------------------
# Card widget (Content Listings)
# -------------------------------------------------------------------


class _SyncBackupWorker(QThread):
    progress = Signal(int, str)  # (percent, text)
    finished = Signal(bool, str, object)  # (success, message, result_data)

    def __init__(self, task_type: str, category: str, params: dict):
        super().__init__()
        self.task_type = task_type
        self.category = category
        self.params = params

    def run(self):
        try:
            if self.task_type == "sync":
                self.run_sync()
            elif self.task_type == "backup":
                self.run_backup()
        except Exception as e:
            self.finished.emit(False, str(e), None)

    def run_sync(self):
        # 1. Load and decrypt remote entries
        self.progress.emit(5, "Loading encrypted backup file...")
        vault_manager = self.params["vault_manager"]
        SecureJsonVault = vault_manager.SecureJsonVault
        secret_key = vault_manager.secret_key
        enc_file_path = self.params["enc_file_path"]

        temp_vault = SecureJsonVault(secret_key, enc_file_path)
        java_str = temp_vault.loadData()
        remote_json_str = str(java_str)
        try:
            remote_entries = json.loads(remote_json_str)
        except Exception:
            remote_entries = []

        # 2. Merge local and remote entries by unique ID
        self.progress.emit(15, "Merging local and remote entries...")
        local_entries = self.params["local_entries"]
        merged_dict = {
            item["id"]: item
            for item in remote_entries
            if isinstance(item, dict) and "id" in item
        }
        for item in local_entries:
            if isinstance(item, dict) and "id" in item:
                merged_dict[item["id"]] = item

        merged_entries = list(merged_dict.values())

        # 3. Save merged entries locally (updates DB)
        self.progress.emit(30, "Preparing database synchronization...")
        db_path = self.params["db_path"]
        password = vault_manager.raw_password
        salt = vault_manager.account_name

        # Delete old rows
        rows = base.fetch_all_listings_secure(db_path, password, salt)
        total_rows = len(rows)
        for i, row in enumerate(rows):
            id_, category, _, _, _ = row
            if self.category == "Content" and category != "Entity":
                base.delete_listing_secure(db_path, password, salt, id_)
            elif self.category == "Entity" and category == "Entity":
                base.delete_listing_secure(db_path, password, salt, id_)
            # Report progress during deletes (up to 40%)
            percent = 30 + int(10 * (i + 1) / (total_rows if total_rows > 0 else 1))
            self.progress.emit(
                percent, f"Cleaning secure database ({i + 1}/{total_rows})..."
            )

        total_inserts = len(merged_entries)
        for i, entry in enumerate(merged_entries):
            eid = entry.get("id")
            if self.category == "Content":
                ecat = entry.get("type", "Anime")
                etitle = entry.get("title", "")
                edate = entry.get("date_added", "")
                meta = dict(entry)
                base.insert_listing_secure(
                    db_path,
                    password,
                    salt,
                    eid,
                    ecat,
                    etitle,
                    json.dumps(meta, ensure_ascii=False),
                    edate,
                    [],
                )
            else:  # Entity
                ename = entry.get("name", "")
                edate = entry.get("date_added", "")
                meta = dict(entry)
                base.insert_listing_secure(
                    db_path,
                    password,
                    salt,
                    eid,
                    "Entity",
                    ename,
                    json.dumps(meta, ensure_ascii=False),
                    edate,
                    [],
                )
            # Report progress during inserts (up to 80%)
            percent = 40 + int(
                40 * (i + 1) / (total_inserts if total_inserts > 0 else 1)
            )
            self.progress.emit(
                percent, f"Writing entries to database ({i + 1}/{total_inserts})..."
            )

        # 4. Sync images from ZIP backup
        self.progress.emit(85, "Restoring images from backup ZIP...")
        prefix = "content_images" if self.category == "Content" else "entity_images"
        synced_imgs = _sync_images_from_backup(prefix)

        self.progress.emit(100, "Done!")
        self.finished.emit(True, "Sync complete", (merged_entries, synced_imgs))

    def run_backup(self):
        self.progress.emit(5, "Encrypting and saving entries...")
        vault_manager = self.params["vault_manager"]
        SecureJsonVault = vault_manager.SecureJsonVault
        secret_key = vault_manager.secret_key
        enc_file_path = self.params["enc_file_path"]
        entries = self.params["entries"]

        temp_vault = SecureJsonVault(secret_key, enc_file_path)
        json_content = json.dumps(entries, indent=2, ensure_ascii=False)
        temp_vault.saveData(json_content)

        self.progress.emit(20, "Creating multi-part ZIP archive of images...")
        prefix = "content_images" if self.category == "Content" else "entity_images"

        referenced_files = set()
        for entry in entries:
            img = entry.get("image_path")
            if img:
                referenced_files.add(Path(img).name)
            for sub in entry.get("episode_list", []) + entry.get("credit_list", []):
                sub_img = sub.get("image_path")
                if sub_img:
                    referenced_files.add(Path(sub_img).name)

        files_to_backup = []
        if referenced_files:
            for filename in referenced_files:
                p = LISTING_IMAGES_DIR / filename
                if p.exists() and p.is_file():
                    files_to_backup.append(p)

        if not files_to_backup:
            self.progress.emit(100, "Done!")
            self.finished.emit(True, "Backup complete", 0)
            return

        migrations_dir = Path(udef.ROOT_DIR) / "assets" / "migrations"
        migrations_dir.mkdir(parents=True, exist_ok=True)

        # Clean up old parts
        for old_part in migrations_dir.glob(f"{prefix}.part*.zip"):
            old_part.unlink()

        part_idx = 1
        max_size_bytes = 100 * 1024 * 1024
        current_zip_path = migrations_dir / f"{prefix}.part{part_idx}.zip"
        zf = zipfile.ZipFile(current_zip_path, "w", zipfile.ZIP_DEFLATED)

        total_files = len(files_to_backup)
        try:
            for i, file_path in enumerate(files_to_backup):
                if (
                    zf.fp.tell() + file_path.stat().st_size > max_size_bytes
                    and zf.filelist
                ):
                    zf.close()
                    part_idx += 1
                    current_zip_path = migrations_dir / f"{prefix}.part{part_idx}.zip"
                    zf = zipfile.ZipFile(current_zip_path, "w", zipfile.ZIP_DEFLATED)
                zf.write(file_path, file_path.name)
                # Report progress (up to 95%)
                percent = 20 + int(75 * (i + 1) / total_files)
                self.progress.emit(percent, f"Archiving image {i + 1}/{total_files}...")
        finally:
            zf.close()

        self.progress.emit(100, "Done!")
        self.finished.emit(True, "Backup complete", len(files_to_backup))
