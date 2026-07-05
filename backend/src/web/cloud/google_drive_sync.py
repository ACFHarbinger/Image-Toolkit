import json
import os
from typing import Any, Callable

import base  # Native extension


class GoogleDriveSync:
    """
    Manages synchronization for Google Drive using the C++ implementation.
    Supports both Service Account and Personal account flows.
    """

    def __init__(
        self,
        local_source_path: str,
        drive_destination_folder_name: str,
        google_json_key_path: str = None,
        google_access_token: str = None,  # Used for personal account
        dry_run: bool = False,
        logger: Callable[[str], None] = print,
        action_local_orphans: str = "upload",
        action_remote_orphans: str = "download",
        service_account_data: Any = None,
        client_secrets_data: Any = None,
        token_file: str = None,
        user_email_to_share_with: str = None,
        **kwargs,
    ):
        SCOPES = ["https://www.googleapis.com/auth/drive"]
        access_token = google_access_token

        # 1. Resolve Service Account Authentication
        if not access_token and service_account_data:
            try:
                from google.auth.transport.requests import Request
                from google.oauth2 import service_account

                if isinstance(service_account_data, str):
                    service_account_data = json.loads(service_account_data)

                creds = service_account.Credentials.from_service_account_info(
                    service_account_data, scopes=SCOPES
                )
                creds.refresh(Request())
                access_token = creds.token
            except Exception as e:
                logger(f"❌ Error obtaining service account access token: {e}")

        # 2. Resolve Personal Account (OAuth2 Flow) Authentication
        if not access_token and client_secrets_data:
            try:
                from google.auth.transport.requests import Request
                from google.oauth2.credentials import Credentials

                if isinstance(client_secrets_data, str):
                    client_secrets_data = json.loads(client_secrets_data)

                creds = None
                if token_file and os.path.exists(token_file):
                    try:
                        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
                    except Exception as e:
                        logger(f"⚠️ Failed to load token file: {e}")

                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        try:
                            creds.refresh(Request())
                        except Exception as e:
                            logger(f"⚠️ Failed to refresh token: {e}")
                            creds = None

                    if not creds or not creds.valid:
                        import subprocess
                        import sys
                        import time

                        helper_path = os.path.join(os.path.dirname(__file__), "gdrive_auth_helper.py")
                        input_payload = {
                            "client_secrets_data": client_secrets_data,
                            "token_file": token_file,
                            "scopes": SCOPES
                        }

                        logger("🔑 Launching Google Drive authentication helper in a separate process...")
                        proc = subprocess.Popen(
                            [sys.executable, helper_path],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )

                        try:
                            # Send configuration to the helper via stdin
                            proc.stdin.write(json.dumps(input_payload))
                            proc.stdin.close()

                            # Poll the helper process while checking for user cancellation
                            while proc.poll() is None:
                                if not getattr(self, "_is_running", True):
                                    logger("🛑 Authentication cancelled by user. Terminating helper process...")
                                    proc.terminate()
                                    proc.wait(timeout=2)
                                    raise Exception("Authentication cancelled by user.")
                                time.sleep(0.5)

                            stdout, stderr = proc.communicate()
                            if proc.returncode != 0:
                                raise Exception(stderr.strip() or f"Helper process exited with code {proc.returncode}")

                            logger("✅ Google authentication completed successfully.")

                            # Reload the credentials from the newly written token file
                            if token_file and os.path.exists(token_file):
                                creds = Credentials.from_authorized_user_file(token_file, SCOPES)
                        except Exception as e:
                            logger(f"❌ Authentication flow failed: {e}")
                            creds = None

                if creds:
                    access_token = creds.token
            except Exception as e:
                logger(f"❌ Error obtaining personal account access token: {e}")

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
        self.user_email_to_share_with = user_email_to_share_with

    def stop(self):
        self._is_running = False

    def on_status_emitted(self, msg: str):
        """Called by C++ to log messages."""
        self.logger(msg)

    def execute_sync(self) -> tuple[bool, str]:
        try:
            config_json = json.dumps(self.config)
            # Use the C++ runner
            result_json = base.run_sync("google_drive", config_json, self)
            stats = json.loads(result_json)

            summary = f"Completed with {stats['uploaded'] + stats['downloaded'] + stats['deleted_local'] + stats['deleted_remote']} actions. (Up: {stats['uploaded']}, Down: {stats['downloaded']}, Del-L: {stats['deleted_local']}, Del-R: {stats['deleted_remote']})"
            return (True, summary)
        except Exception as e:
            self.logger(f"❌ Critical Error in C++ Sync: {e}")
            return (False, str(e))
