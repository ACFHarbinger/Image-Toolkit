"""Per-file Dropbox v2 REST client for Local Directory Sync (#479).

``DropboxDriveSync`` (the C++ ``base`` extension) only does a whole-folder
one-way sync and exposes no per-file API. ``LocalDirSyncWorker`` needs
``list_remote_files`` / ``upload_file`` / ``download_file`` against a named
root folder with nested relative paths — this provides them in pure Python
using the Dropbox v2 REST API (files/list_folder, files/upload, files/download)
with the OAuth access token configured in the vault.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

import requests

_API_RPC = "https://api.dropboxapi.com/2"
_API_CONTENT = "https://content.dropboxapi.com/2"
_TIMEOUT = 60


class DropboxFileClient:
    """Path-addressed file ops within one Dropbox folder tree."""

    def __init__(
        self,
        access_token: str,
        root_name: str = ".image-toolkit",
        logger: Callable[[str], None] = print,
    ) -> None:
        if not access_token:
            raise ValueError("DropboxFileClient needs a valid access_token")
        self._token = access_token
        self._s = requests.Session()
        self._s.headers["Authorization"] = f"Bearer {access_token}"
        root_clean = root_name.strip("/")
        self._root_path = f"/{root_clean}" if root_clean else ""
        self._log = logger

    def _rpc_post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> requests.Response:
        url = f"{_API_RPC}/{endpoint.lstrip('/')}"
        r = self._s.post(url, json=json_data or {}, timeout=_TIMEOUT)
        return r

    @staticmethod
    def _mtime(iso: str) -> float:
        from datetime import datetime

        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    def _full_remote_path(self, relpath: str) -> str:
        clean_rel = relpath.strip("/")
        if not self._root_path:
            return f"/{clean_rel}" if clean_rel else ""
        return f"{self._root_path}/{clean_rel}" if clean_rel else self._root_path

    def ensure_folder(self, rel_dir: str) -> None:
        """Create remote folder path if it does not already exist."""
        path = self._full_remote_path(rel_dir)
        if not path:
            return
        r = self._rpc_post("files/create_folder_v2", {"path": path, "autorename": False})
        if r.status_code not in (200, 409):
            r.raise_for_status()

    def list_remote_files(self) -> List[Dict[str, Any]]:
        """Recursive listing under the root folder -> [{path, mtime, size}]."""
        result: List[Dict[str, Any]] = []
        payload = {
            "path": self._root_path,
            "recursive": True,
            "include_media_info": False,
            "include_deleted": False,
            "include_has_explicit_shared_members": False,
            "include_mounted_folders": True,
        }

        r = self._rpc_post("files/list_folder", payload)
        if r.status_code == 409:
            # Path not found: folder does not exist yet remotely
            return []
        r.raise_for_status()
        data = r.json()

        entries = list(data.get("entries", []))
        cursor = data.get("cursor")
        has_more = data.get("has_more", False)

        while has_more and cursor:
            r_cont = self._rpc_post("files/list_folder/continue", {"cursor": cursor})
            r_cont.raise_for_status()
            data_cont = r_cont.json()
            entries.extend(data_cont.get("entries", []))
            cursor = data_cont.get("cursor")
            has_more = data_cont.get("has_more", False)

        root_prefix = self._root_path.rstrip("/") + "/"
        prefix_len = len(root_prefix) if self._root_path else 1

        for entry in entries:
            tag = entry.get(".tag", "")
            if tag == "file":
                path_display = entry.get("path_display", "")
                if self._root_path and path_display.lower().startswith(self._root_path.lower() + "/"):
                    relpath = path_display[prefix_len:].lstrip("/")
                else:
                    relpath = path_display.lstrip("/")
                mtime_str = entry.get("server_modified") or entry.get("client_modified", "")
                result.append(
                    {
                        "path": relpath,
                        "mtime": self._mtime(mtime_str),
                        "size": int(entry.get("size", 0) or 0),
                    }
                )
        return result

    def upload_file(self, local_abs: str, relpath: str) -> None:
        """Upload a local file to Dropbox at the relative path under root."""
        remote_path = self._full_remote_path(relpath)
        url = f"{_API_CONTENT}/files/upload"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/octet-stream",
            "Dropbox-API-Arg": json.dumps({
                "path": remote_path,
                "mode": "overwrite",
                "autorename": False,
                "mute": False,
                "strict_conflict": False,
            }),
        }
        with open(local_abs, "rb") as fh:
            r = self._s.post(url, headers=headers, data=fh, timeout=_TIMEOUT)
        r.raise_for_status()

    def download_file(self, relpath: str, local_abs: str) -> None:
        """Download a remote file from Dropbox to local_abs path."""
        remote_path = self._full_remote_path(relpath)
        url = f"{_API_CONTENT}/files/download"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Dropbox-API-Arg": json.dumps({"path": remote_path}),
        }
        os.makedirs(os.path.dirname(local_abs) or ".", exist_ok=True)
        r = self._s.post(url, headers=headers, stream=True, timeout=_TIMEOUT)
        if r.status_code == 409:
            raise FileNotFoundError(f"remote file not found: {relpath}")
        r.raise_for_status()
        with open(local_abs, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)


__all__ = ["DropboxFileClient"]
