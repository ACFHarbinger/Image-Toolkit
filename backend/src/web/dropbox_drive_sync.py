import json
import base # Native extension
from typing import Callable, Optional

class DropboxDriveSync:
    """
    Manages synchronization for Dropbox using the Rust implementation.
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
        self.config = {
            "local_path": local_source_path,
            "remote_path": drive_destination_folder_name,
            "access_token": access_token,
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
            result_json = base.run_sync("dropbox", config_json, self)
            stats = json.loads(result_json)
            
            summary = f"Completed with {stats['uploaded'] + stats['downloaded'] + stats['deleted_local'] + stats['deleted_remote']} actions. (Up: {stats['uploaded']}, Down: {stats['downloaded']}, Del-L: {stats['deleted_local']}, Del-R: {stats['deleted_remote']})"
            return (True, summary)
        except Exception as e:
            self.logger(f"❌ Critical Error in Rust Sync: {e}")
            return (False, str(e))
