import json
import platform
import re
import shutil
import subprocess
import zipfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import backend.src.constants as udef
import base
import cv2
from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QLabel

from gui.src.components.dialogs.frame_selection_dialog import (
    extract_video_frame_via_ffmpeg,
)
from .....constants.listings import (
    ENTITIES_FILE,  # noqa: F401
    LISTING_IMAGES_DIR,
    LISTINGS_FILE,  # noqa: F401
    VIDEO_IMPORT_EXTS,
)


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

    base.insert_listing_secure( # pyrefly: ignore [missing-attribute]
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

    base.insert_listing_secure( # pyrefly: ignore [missing-attribute]
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
            if zf.fp.tell() + file_path.stat().st_size > max_size_bytes and zf.filelist: # pyrefly: ignore [missing-attribute]
                zf.close()
                part_idx += 1
                current_zip_path = migrations_dir / f"{prefix}.part{part_idx}.zip"
                zf = zipfile.ZipFile(current_zip_path, "w", zipfile.ZIP_DEFLATED)
            zf.write(file_path, file_path.name)
    finally:
        zf.close()

    return len(files_to_backup)


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
    from gui.src.windows.settings.app_settings import AppSettings
    state = AppSettings.listings_splitter(key)
    if state:
        splitter.restoreState(state)

    splitter.splitterMoved.connect(
        lambda: AppSettings.set_listings_splitter(key, splitter.saveState())
    )


def generate_thumbnail_from_file(file_path: str, dest_path: str) -> bool:  # noqa: C901
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
    """Scan *directory* for video files.

    Returns ``{series_name: [(ep_num_or_None, abs_path), ...]}`` with each
    series' list sorted by episode number (None episodes go last).
    """
    from gui.src.windows.settings.app_settings import AppSettings
    recursive = AppSettings.recursive_scan()

    result: dict = {}
    dir_path = Path(directory)
    try:
        if recursive:
            entries = sorted(dir_path.rglob("*"), key=lambda e: e.name.lower())
        else:
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


def normalize_id_list(raw) -> List[str]:
    """Coerce associated-ID fields from JSON into a list of non-empty strings."""
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _mal_name_lookup_key(name: str) -> str:
    return name.strip().lower()


def resolve_entity_id_for_mal_name(
    name: str, name_index: Dict[str, str]
) -> Optional[str]:
    """Match a MAL person/org name against local entity display names.

    Tries exact match, single-name duplication (``Tomoko`` → ``Tomoko Tomoko``),
    reversed multi-word order, and ``Last, First`` → ``First Last`` forms.
    """
    if not name or not name.strip():
        return None

    key = _mal_name_lookup_key(name)
    eid = name_index.get(key)
    if eid is not None:
        return eid

    words = name.split()
    if len(words) == 1:
        duplicate = _mal_name_lookup_key(f"{words[0]} {words[0]}")
        eid = name_index.get(duplicate)
        if eid is not None:
            return eid
    elif len(words) >= 2:
        eid = name_index.get(_mal_name_lookup_key(" ".join(reversed(words))))
        if eid is not None:
            return eid

    if ", " in name:
        last, first = name.split(", ", 1)
        eid = name_index.get(_mal_name_lookup_key(f"{first} {last}"))
        if eid is not None:
            return eid

    return None


def fetch_entity_name_map(db_path: str, password: str, salt: str) -> Dict[str, str]:
    """Return ``{entity_id: display_name}`` from the secure listings database."""
    name_map: Dict[str, str] = {}
    try:
        rows = base.fetch_all_listings_secure(db_path, password, salt)  # pyrefly: ignore [missing-attribute]
        for row in rows:
            id_, category, title, _, _ = row
            if category == "Entity":
                name_map[str(id_)] = title
    except Exception as e:
        print(f"Failed to load entity names: {e}")
    return name_map


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

