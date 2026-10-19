"""Per-file Microsoft OneDrive (MS Graph) client for Local Directory Sync (#479).

``OneDriveSync`` (the C++ ``base`` extension) only does a whole-folder one-way
sync and exposes no per-file API. ``LocalDirSyncWorker`` needs
``list_remote_files`` / ``upload_file`` / ``download_file`` against a named
root folder with nested relative paths — this provides them in pure Python
using the Microsoft Graph Drive API (``graph.microsoft.com/v1.0``) with the
OAuth access token configured in the vault.

Uses the addressable-path form ``root:/<path>:/children`` for listing and
``root:/<path>:/content`` for upload/download. Files are addressed as a single
drive item each, relative to ``root_name`` under the user's OneDrive root.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List
from urllib.parse import quote

import requests

_API = "https://graph.microsoft.com/v1.0"
_TIMEOUT = 60


class OneDriveFileClient:
    """Path-addressed file ops within one OneDrive folder tree."""

    def __init__(
        self,
        access_token: str,
        root_name: str = ".image-toolkit",
        logger: Callable[[str], None] = print,
    ) -> None:
        if not access_token:
            raise ValueError("OneDriveFileClient needs a valid access_token")
        self._s = requests.Session()
        self._s.headers["Authorization"] = f"Bearer {access_token}"
        self._root_name = root_name.strip("/")
        self._log = logger

    # ------------------------------------------------------------------ helpers
    def _full_path(self, relpath: str) -> str:
        """Map a path relative to root_name to its drive-root-relative path."""
        rel = relpath.strip("/")
        if not self._root_name:
            return rel
        return f"{self._root_name}/{rel}" if rel else self._root_name

    @staticmethod
    def _mtime(iso: str) -> float:
        # Graph lastModifiedDateTime is RFC3339 UTC, e.g. 2026-08-31T18:20:02.123Z
        from datetime import datetime

        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    def _item_url(self, full_path: str, tail: str) -> str:
        """Build an addressable-path URL.

        ``full_path`` is drive-root-relative (``.image-toolkit/config``).
        ``tail`` is ``/children``, ``/content`` or ``""`` (metadata).
        """
        if not full_path:
            return f"{_API}/me/drive/root{tail}"
        segment = quote(full_path, safe="/")
        return f"{_API}/me/drive/root:/{segment}:{tail}"

    def _get(self, url: str, **kw) -> requests.Response:
        r = self._s.get(url, timeout=_TIMEOUT, **kw)
        if r.status_code >= 400:
            r.raise_for_status()
        return r

    def _children(self, rel_dir: str) -> List[Dict[str, Any]]:
        """List the drive items under ``rel_dir`` (relative to root_name)."""
        url = self._item_url(self._full_path(rel_dir), "/children")
        out: List[Dict[str, Any]] = []
        # If the root folder does not exist yet remotely, Graph returns 404 —
        # treat that as an empty tree, matching the other per-file clients.
        while url:
            r = self._s.get(url, timeout=_TIMEOUT)
            if r.status_code == 404:
                return out
            r.raise_for_status()
            data = r.json()
            out.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
        return out

    def _folder_exists(self, full_path: str) -> bool:
        """True if ``full_path`` resolves to an existing folder."""
        r = self._s.get(self._item_url(full_path, ""), timeout=_TIMEOUT)
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return "folder" in r.json()

    def _create_folder(self, full_path: str) -> None:
        parent, _, name = full_path.rpartition("/")
        url = self._item_url(parent, "/children") if parent else f"{_API}/me/drive/root/children"
        body: Dict[str, Any] = {
            "name": name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "replace",
        }
        r = self._s.post(url, json=body, timeout=_TIMEOUT)
        if r.status_code not in (200, 201, 204, 409):
            r.raise_for_status()

    def ensure_folder(self, rel_dir: str) -> None:
        """Create the remote folder path (and any missing ancestors) if needed."""
        rel = rel_dir.strip("/")
        if not rel or rel == ".":
            rel = ""
        full_dir = self._full_path(rel)
        if not full_dir:
            return
        current = ""
        for part in full_dir.split("/"):
            current = f"{current}/{part}" if current else part
            if not self._folder_exists(current):
                self._log(f"Creating remote folder '{part}'…")
                self._create_folder(current)

    # ----------------------------------------------------- the worker interface
    def list_remote_files(self) -> List[Dict[str, Any]]:
        """Recursive listing under the root → [{path, mtime, size}]."""
        result: List[Dict[str, Any]] = []
        stack: List[str] = [""]
        while stack:
            rel = stack.pop()
            for item in self._children(rel):
                name = item.get("name", "")
                child_rel = f"{rel}/{name}".strip("/") if (rel and name) else name
                if "folder" in item:
                    stack.append(child_rel)
                elif "file" in item:
                    result.append(
                        {
                            "path": child_rel,
                            "mtime": self._mtime(item.get("lastModifiedDateTime", "")),
                            "size": int((item.get("file") or {}).get("size", 0) or 0),
                        }
                    )
        return result

    def upload_file(self, local_abs: str, relpath: str) -> None:
        """Upload a local file to OneDrive at the relative path under root."""
        rel_dir, _, name = relpath.strip("/").rpartition("/")
        self.ensure_folder(rel_dir)
        url = self._item_url(self._full_path(relpath), "/content")
        with open(local_abs, "rb") as fh:
            r = self._s.put(url, data=fh, timeout=_TIMEOUT)
        if r.status_code not in (200, 201, 204):
            r.raise_for_status()

    def download_file(self, relpath: str, local_abs: str) -> None:
        """Download a remote file from OneDrive to local_abs path."""
        url = self._item_url(self._full_path(relpath), "/content")
        r = self._s.get(url, stream=True, timeout=_TIMEOUT)
        if r.status_code == 404:
            raise FileNotFoundError(f"remote file not found: {relpath}")
        r.raise_for_status()
        os.makedirs(os.path.dirname(local_abs) or ".", exist_ok=True)
        with open(local_abs, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)


__all__ = ["OneDriveFileClient"]
