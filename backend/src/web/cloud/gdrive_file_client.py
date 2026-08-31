"""Per-file Google Drive v3 REST client for Local Directory Sync (#479).

``GoogleDriveSync`` (the C++ ``base`` extension) only does a whole-folder
one-way sync and exposes no per-file API. ``LocalDirSyncWorker`` needs
``list_remote_files`` / ``upload_file`` / ``download_file`` against a named
root folder with nested relative paths — this provides them in pure Python
using the OAuth access token ``GoogleDriveSync`` already resolves.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

import requests

_API = "https://www.googleapis.com/drive/v3"
_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
_FOLDER_MIME = "application/vnd.google-apps.folder"
_TIMEOUT = 60


class GoogleDriveFileClient:
    """Path-addressed file ops within one Drive folder tree."""

    def __init__(
        self,
        access_token: str,
        root_name: str = ".image-toolkit",
        logger: Callable[[str], None] = print,
    ) -> None:
        if not access_token:
            raise ValueError("GoogleDriveFileClient needs a valid access_token")
        self._s = requests.Session()
        self._s.headers["Authorization"] = f"Bearer {access_token}"
        self._root_name = root_name
        self._log = logger
        self._root_id: Optional[str] = None
        # relative-dir -> folder id (""/"." == root)
        self._dir_ids: Dict[str, str] = {}

    # ------------------------------------------------------------------ helpers
    def _get(self, url: str, **kw) -> requests.Response:
        r = self._s.get(url, timeout=_TIMEOUT, **kw)
        r.raise_for_status()
        return r

    def _q(self, query: str) -> List[Dict[str, Any]]:
        """Run a files.list query, following pagination."""
        out: List[Dict[str, Any]] = []
        page = None
        while True:
            params = {
                "q": query,
                "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,size)",
                "pageSize": 1000,
                "spaces": "drive",
            }
            if page:
                params["pageToken"] = page
            data = self._get(f"{_API}/files", params=params).json()
            out.extend(data.get("files", []))
            page = data.get("nextPageToken")
            if not page:
                return out

    @staticmethod
    def _mtime(iso: str) -> float:
        # Drive modifiedTime is RFC3339 UTC, e.g. 2026-08-31T18:20:02.123Z
        from datetime import datetime

        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    def _root(self) -> str:
        if self._root_id:
            return self._root_id
        hits = self._q(
            f"name = '{self._root_name}' and mimeType = '{_FOLDER_MIME}' "
            f"and 'root' in parents and trashed = false"
        )
        if hits:
            self._root_id = hits[0]["id"]
        else:
            self._log(f"Creating remote folder '{self._root_name}'…")
            r = self._s.post(
                f"{_API}/files",
                json={"name": self._root_name, "mimeType": _FOLDER_MIME, "parents": ["root"]},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            self._root_id = r.json()["id"]
        self._dir_ids[""] = self._root_id
        return self._root_id

    def ensure_folder(self, rel_dir: str) -> str:
        """Return the id of ``rel_dir`` under the root, creating each segment."""
        rel_dir = rel_dir.strip("/")
        if rel_dir in ("", "."):
            return self._root()
        if rel_dir in self._dir_ids:
            return self._dir_ids[rel_dir]
        parent_rel, _, name = rel_dir.rpartition("/")
        parent_id = self.ensure_folder(parent_rel)
        hits = self._q(
            f"name = '{name}' and mimeType = '{_FOLDER_MIME}' "
            f"and '{parent_id}' in parents and trashed = false"
        )
        if hits:
            fid = hits[0]["id"]
        else:
            r = self._s.post(
                f"{_API}/files",
                json={"name": name, "mimeType": _FOLDER_MIME, "parents": [parent_id]},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            fid = r.json()["id"]
        self._dir_ids[rel_dir] = fid
        return fid

    def _file_id(self, relpath: str) -> Optional[str]:
        rel_dir, _, name = relpath.strip("/").rpartition("/")
        parent = self.ensure_folder(rel_dir)
        hits = self._q(
            f"name = '{name}' and '{parent}' in parents and trashed = false"
        )
        return hits[0]["id"] if hits else None

    # ----------------------------------------------------- the worker interface
    def list_remote_files(self) -> List[Dict[str, Any]]:
        """Recursive listing under the root → [{path, mtime, size}]."""
        result: List[Dict[str, Any]] = []
        # BFS over folders, tracking relative path.
        stack = [("", self._root())]
        while stack:
            rel, fid = stack.pop()
            for f in self._q(f"'{fid}' in parents and trashed = false"):
                child_rel = f"{rel}/{f['name']}".lstrip("/")
                if f["mimeType"] == _FOLDER_MIME:
                    self._dir_ids[child_rel] = f["id"]
                    stack.append((child_rel, f["id"]))
                else:
                    result.append(
                        {
                            "path": child_rel,
                            "mtime": self._mtime(f.get("modifiedTime", "")),
                            "size": int(f.get("size", 0) or 0),
                        }
                    )
        return result

    def upload_file(self, local_abs: str, relpath: str) -> None:
        rel_dir, _, name = relpath.strip("/").rpartition("/")
        parent = self.ensure_folder(rel_dir)
        existing = self._file_id(relpath)
        meta: Dict[str, Any] = {"name": name}
        if existing:
            url = f"{_UPLOAD}/{existing}?uploadType=multipart"
            method = self._s.patch
        else:
            meta["parents"] = [parent]
            url = f"{_UPLOAD}?uploadType=multipart"
            method = self._s.post
        with open(local_abs, "rb") as fh:
            files = {
                "metadata": ("metadata", _json(meta), "application/json; charset=UTF-8"),
                "file": (name, fh, "application/octet-stream"),
            }
            r = method(url, files=files, timeout=_TIMEOUT)
        r.raise_for_status()

    def download_file(self, relpath: str, local_abs: str) -> None:
        fid = self._file_id(relpath)
        if not fid:
            raise FileNotFoundError(f"remote file not found: {relpath}")
        os.makedirs(os.path.dirname(local_abs) or ".", exist_ok=True)
        with self._get(
            f"{_API}/files/{fid}", params={"alt": "media"}, stream=True
        ) as r, open(local_abs, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)


def _json(obj: Dict[str, Any]) -> str:
    import json

    return json.dumps(obj)


__all__ = ["GoogleDriveFileClient"]
