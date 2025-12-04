import os
import shutil
import dropbox

from typing import Callable, Dict, Any
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError, AuthError


class DropboxDriveSync:
    """
    Manages synchronization for Dropbox using the official Dropbox Python SDK.
    """

    def __init__(
        self,
        local_source_path: str,
        drive_destination_folder_name: str,
        access_token: str = None,
        dry_run: bool = False,
        logger: Callable[[str], None] = print,
        action_local_orphans: str = "upload",
        action_remote_orphans: str = "download",
    ):
        self.local_path = local_source_path
        # Dropbox paths must start with /
        self.remote_path = "/" + drive_destination_folder_name.strip("/")
        if self.remote_path == "/":
            self.remote_path = ""  # Root folder case

        self.access_token = access_token
        self.dry_run = dry_run
        self.logger = logger
        self.action_local = action_local_orphans
        self.action_remote = action_remote_orphans
        self._is_running = True
        self.dbx = None

    def check_stop(self):
        if not self._is_running:
            raise InterruptedError("Synchronization manually interrupted.")

    def _get_local_files_map(self) -> Dict[str, Dict[str, Any]]:
        """Creates a map of relative_path -> (absolute_path, timestamp) for local files."""
        local_items = {}
        base_len = len(self.local_path) + len(os.sep)

        for root, dirs, files in os.walk(self.local_path):
            self.check_stop()
            # Process Files
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = abs_path[base_len:].replace(os.sep, "/")
                local_items[rel_path] = {
                    "path": abs_path,
                    "mtime": int(os.path.getmtime(abs_path)),
                    "is_folder": False,
                }
            # Process Folders (Empty folders matter for structure)
            for d in dirs:
                abs_path = os.path.join(root, d)
                rel_path = abs_path[base_len:].replace(os.sep, "/")
                local_items[rel_path] = {
                    "path": abs_path,
                    "mtime": int(os.path.getmtime(abs_path)),
                    "is_folder": True,
                }
        return local_items

    def _get_remote_files_map(self) -> Dict[str, Dict[str, Any]]:
        """
        Recursively lists all files in the remote folder.
        Returns map: relative_path -> metadata
        """
        remote_items = {}
        try:
            self.logger(f"🔍 Scanning remote folder: {self.remote_path}")

            # Dropbox list_folder is recursive if recursive=True
            # If the folder doesn't exist, list_folder might throw an error or return empty
            try:
                res = self.dbx.files_list_folder(self.remote_path, recursive=True)
            except ApiError as e:
                if e.error.is_path() and e.error.get_path().is_not_found():
                    self.logger(
                        "   Remote folder does not exist yet (will be created)."
                    )
                    return {}
                raise

            def process_entries(entries):
                for entry in entries:
                    self.check_stop()
                    # Calculate relative path from the synchronization root
                    # entry.path_display is absolute in Dropbox (e.g., /Backup/2025/file.txt)
                    # We need 'file.txt' if remote_path is '/Backup/2025'

                    # Strip the root prefix. Handle case sensitivity carefully if needed.
                    # Dropbox paths are case-insensitive but case-preserving.
                    full_dbx_path = entry.path_display
                    if self.remote_path == "":
                        rel_path = full_dbx_path.strip("/")
                    else:
                        if full_dbx_path.lower().startswith(self.remote_path.lower()):
                            rel_path = full_dbx_path[len(self.remote_path) :].strip("/")
                        else:
                            continue  # Should not happen with recursive list of specific folder

                    if not rel_path:
                        continue  # Skip the root folder itself

                    is_folder = isinstance(entry, dropbox.files.FolderMetadata)
                    mtime = 0
                    if isinstance(entry, dropbox.files.FileMetadata):
                        mtime = int(entry.client_modified.timestamp())

                    remote_items[rel_path] = {
                        "path_lower": entry.path_lower,  # Use lower for API calls
                        "path_display": entry.path_display,
                        "mtime": mtime,
                        "is_folder": is_folder,
                    }

            process_entries(res.entries)

            while res.has_more:
                self.check_stop()
                res = self.dbx.files_list_folder_continue(res.cursor)
                process_entries(res.entries)

            return remote_items

        except ApiError as e:
            self.logger(f"❌ Dropbox API Error listing files: {e}")
            raise

    def _upload_file(self, local_path: str, rel_path: str):
        self.check_stop()
        # Dropbox paths must start with /
        target_path = f"{self.remote_path}/{rel_path}"

        if self.dry_run:
            self.logger(f"   [DRY RUN] UPLOAD: {rel_path}")
            return True

        try:
            with open(local_path, "rb") as f:
                # Use WriteMode.overwrite to handle conflicts if logic failed elsewhere
                self.dbx.files_upload(
                    f.read(), target_path, mode=WriteMode("overwrite")
                )
            return True
        except ApiError as e:
            self.logger(f"❌ Error uploading {rel_path}: {e}")
            return False

    def _create_remote_folder(self, rel_path: str):
        self.check_stop()
        target_path = f"{self.remote_path}/{rel_path}"

        if self.dry_run:
            self.logger(f"   [DRY RUN] CREATE FOLDER: {rel_path}")
            return True

        try:
            self.dbx.files_create_folder_v2(target_path)
            return True
        except ApiError as e:
            # Ignore if folder already exists
            if e.error.is_path() and e.error.get_path().is_conflict():
                return True
            self.logger(f"❌ Error creating remote folder {rel_path}: {e}")
            return False

    def _download_file(self, dbx_path: str, local_dest: str):
        self.check_stop()
        if self.dry_run:
            self.logger(
                f"   [DRY RUN] DOWNLOAD: {dbx_path} -> {os.path.basename(local_dest)}"
            )
            return True

        try:
            os.makedirs(os.path.dirname(local_dest), exist_ok=True)
            self.dbx.files_download_to_file(local_dest, dbx_path)
            return True
        except ApiError as e:
            self.logger(f"❌ Error downloading {dbx_path}: {e}")
            return False

    def _delete_local(self, local_path: str):
        self.check_stop()
        if not os.path.exists(local_path):
            return True

        if self.dry_run:
            self.logger(f"   [DRY RUN] DELETE LOCAL: {local_path}")
            return True

        try:
            if os.path.isdir(local_path):
                shutil.rmtree(local_path)
            else:
                os.remove(local_path)
            return True
        except Exception as e:
            self.logger(f"❌ Error deleting local {local_path}: {e}")
            return False

    def _delete_remote(self, dbx_path: str):
        self.check_stop()
        if self.dry_run:
            self.logger(f"   [DRY RUN] DELETE REMOTE: {dbx_path}")
            return True

        try:
            self.dbx.files_delete_v2(dbx_path)
            return True
        except ApiError as e:
            self.logger(f"❌ Error deleting remote {dbx_path}: {e}")
            return False

    def execute_sync(self) -> tuple[bool, str]:
        try:
            self.logger("🔑 Authenticating with Dropbox...")
            if not self.access_token:
                raise ValueError("Dropbox Access Token is missing.")

            self.dbx = dropbox.Dropbox(self.access_token)
            # Check user to verify token
            try:
                self.dbx.users_get_current_account()
                self.logger("✅ Authentication successful.")
            except AuthError:
                return (False, "Invalid Dropbox Access Token.")

            self.check_stop()
            if not os.path.exists(self.local_path):
                return (False, f"Local path '{self.local_path}' does not exist.")

            # 1. Scan Files
            self.logger("📋 Scanning local and remote files...")
            local_items = self._get_local_files_map()
            remote_items = self._get_remote_files_map()

            self.logger(f"   Found {len(local_items)} local items.")
            self.logger(f"   Found {len(remote_items)} remote items.")

            # 2. Analyze & Execute
            items_uploaded = 0
            items_downloaded = 0
            items_deleted_local = 0
            items_deleted_remote = 0
            items_skipped = 0
            items_ignored = 0

            items_skipped_remote = remote_items.copy()

            # --- Process Local Items ---
            for rel_path, local_data in local_items.items():
                self.check_stop()

                if local_data["is_folder"]:
                    if rel_path in items_skipped_remote:
                        items_skipped_remote.pop(rel_path)  # Match found
                    else:
                        # Folder is local only
                        if self.action_local == "upload":
                            if self._create_remote_folder(rel_path):
                                items_uploaded += (
                                    1  # Count folder creation as action? Optional.
                                )
                        elif self.action_local == "delete_local":
                            self.logger(f"   DELETING LOCAL FOLDER: {rel_path}")
                            if self._delete_local(local_data["path"]):
                                items_deleted_local += 1
                        elif self.action_local == "ignore_local":
                            items_ignored += 1
                    continue

                # File Logic
                remote_data = items_skipped_remote.get(rel_path)

                if remote_data:
                    # Exists in both
                    # Simple existence check (could add hash/mtime check here for updates)
                    items_skipped += 1
                    items_skipped_remote.pop(rel_path)
                else:
                    # Local Orphan
                    if self.action_local == "upload":
                        self.logger(f"   UPLOADING: {rel_path}")
                        if self._upload_file(local_data["path"], rel_path):
                            items_uploaded += 1
                    elif self.action_local == "delete_local":
                        self.logger(f"   DELETING LOCAL: {rel_path}")
                        if self._delete_local(local_data["path"]):
                            items_deleted_local += 1
                    elif self.action_local == "ignore_local":
                        self.logger(f"   IGNORING LOCAL: {rel_path}")
                        items_ignored += 1

            # --- Process Remote Orphans ---
            for rel_path, remote_data in items_skipped_remote.items():
                self.check_stop()

                if remote_data["is_folder"]:
                    # If we are downloading, we create local dirs as needed during file download
                    # If deleting remote, we handle it here
                    if self.action_remote == "delete_remote":
                        self.logger(f"   DELETING REMOTE FOLDER: {rel_path}")
                        if self._delete_remote(remote_data["path_lower"]):
                            items_deleted_remote += 1
                    continue

                # File Logic
                if self.action_remote == "download":
                    self.logger(f"   DOWNLOADING: {rel_path}")
                    local_dest = os.path.join(self.local_path, rel_path)
                    if self._download_file(remote_data["path_lower"], local_dest):
                        items_downloaded += 1

                elif self.action_remote == "delete_remote":
                    self.logger(f"   DELETING REMOTE: {rel_path}")
                    if self._delete_remote(remote_data["path_lower"]):
                        items_deleted_remote += 1

                elif self.action_remote == "ignore_remote":
                    self.logger(f"   IGNORING REMOTE: {rel_path}")
                    items_ignored += 1

            total = (
                items_uploaded
                + items_downloaded
                + items_deleted_local
                + items_deleted_remote
            )

            self.logger("\n--- Sync Execution Summary ---")
            if total == 0 and items_ignored == 0:
                msg = "No changes needed."
            else:
                prefix = "Simulated" if self.dry_run else "Completed"
                msg = f"{prefix} {total} actions. (Up: {items_uploaded}, Down: {items_downloaded}, Del-L: {items_deleted_local}, Del-R: {items_deleted_remote})"

            self.logger(f"✅ {msg}")
            return (True, msg)

        except Exception as e:
            self.logger(f"❌ Critical Error: {e}")
            return (False, str(e))
