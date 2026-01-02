import json
import base # Native extension
from typing import Callable, Optional

class GoogleDriveSync:
    """
    Manages synchronization for Google Drive using the Rust implementation.
    Supports both Service Account and Personal account flows.
    """

    def __init__(
        self,
        local_source_path: str,
        drive_destination_folder_name: str,
        google_json_key_path: str = None,
        google_access_token: str = None, # Used for personal account
        dry_run: bool = False,
        logger: Callable[[str], None] = print,
        action_local_orphans: str = "upload",
        action_remote_orphans: str = "download",
    ):
        # Note: If google_json_key_path is provided, Rust implementation 
        # would ideally handle token exchange. For now, we assume token is passed.
        # If we need service account support in Rust, we'd add JSON key parsing there.
        
        self.config = {
            "local_path": local_source_path,
            "remote_path": drive_destination_folder_name,
            "access_token": google_access_token,
            "dry_run": dry_run,
            "action_local": action_local_orphans,
            "action_remote": action_remote_orphans,
        }
        self.logger = logger
        self._is_running = True

    def stop(self):
        self._is_running = False

    def on_status_emitted(self, msg: str):
        """Called by Rust to log messages."""
        self.logger(msg)

    def execute_sync(self) -> tuple[bool, str]:
        try:
            config_json = json.dumps(self.config)
            # Use the Rust runner
            result_json = base.run_sync("google_drive", config_json, self)
            stats = json.loads(result_json)
            
            summary = f"Completed with {stats['uploaded'] + stats['downloaded'] + stats['deleted_local'] + stats['deleted_remote']} actions. (Up: {stats['uploaded']}, Down: {stats['downloaded']}, Del-L: {stats['deleted_local']}, Del-R: {stats['deleted_remote']})"
            return (True, summary)
        except Exception as e:
            self.logger(f"❌ Critical Error in Rust Sync: {e}")
            return (False, str(e))
