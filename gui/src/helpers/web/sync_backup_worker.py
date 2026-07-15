"""Background worker for synchronising / backing-up encrypted listing files.

Sync target is the unified library database (Phase DB, DB.5): a session
``base.database.Database`` handle is passed in ``params["db"]`` — its
internal mutex makes cross-thread use from this QThread safe — and rows are
merged through the legacy-dict repos instead of the old delete-all/reinsert
against ``listings_secure.db`` (the pattern behind the data-loss incident).
"""

import json
import zipfile
from pathlib import Path

import backend.src.constants as udef
from backend.src.database.unified.entity_repo import EntityRepo
from backend.src.database.unified.media_repo import MediaRepo
from gui.src.constants.listings import LISTING_IMAGES_DIR
from PySide6.QtCore import QThread, Signal


def _sync_images_from_backup(prefix: str) -> int:
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


class _SyncBackupWorker(QThread):
    progress = Signal(int, str)  # (percent, text)
    sig_finished = Signal(bool, str, object)  # (success, message, result_data)

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
            self.sig_finished.emit(False, str(e), None)

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

        # 3. Save merged entries into the unified library (upsert by id —
        #    no delete-then-reinsert window).
        self.progress.emit(30, "Preparing database synchronization...")
        db = self.params["db"]
        repo = MediaRepo(db) if self.category == "Content" else EntityRepo(db)

        total_inserts = len(merged_entries)
        for i, entry in enumerate(merged_entries):
            if self.category == "Content":
                repo.save_media(dict(entry))
            else:
                repo.save_entity(dict(entry))
            percent = 30 + int(50 * (i + 1) / (total_inserts if total_inserts > 0 else 1))
            self.progress.emit(
                percent, f"Writing entries to database ({i + 1}/{total_inserts})..."
            )

        # 4. Sync images from ZIP backup
        self.progress.emit(85, "Restoring images from backup ZIP...")
        prefix = "content_images" if self.category == "Content" else "entity_images"
        synced_imgs = _sync_images_from_backup(prefix)

        self.progress.emit(100, "Done!")
        self.sig_finished.emit(True, "Sync complete", (merged_entries, synced_imgs))

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
            self.sig_finished.emit(True, "Backup complete", 0)
            return

        migrations_dir = Path(udef.ROOT_DIR) / "assets" / "migrations"
        migrations_dir.mkdir(parents=True, exist_ok=True)

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
                    zf.fp.tell() + file_path.stat().st_size > max_size_bytes # pyrefly: ignore [missing-attribute]
                    and zf.filelist
                ):
                    zf.close()
                    part_idx += 1
                    current_zip_path = migrations_dir / f"{prefix}.part{part_idx}.zip"
                    zf = zipfile.ZipFile(current_zip_path, "w", zipfile.ZIP_DEFLATED)
                zf.write(file_path, file_path.name)
                percent = 20 + int(75 * (i + 1) / total_files)
                self.progress.emit(percent, f"Archiving image {i + 1}/{total_files}...")
        finally:
            zf.close()

        self.progress.emit(100, "Done!")
        self.sig_finished.emit(True, "Backup complete", len(files_to_backup))
