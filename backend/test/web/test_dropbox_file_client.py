"""DropboxFileClient — path-addressed Dropbox v2 ops, fully mocked HTTP."""

from __future__ import annotations

import json

import pytest

from backend.src.web.cloud.dropbox_file_client import DropboxFileClient


class _Resp:
    def __init__(self, payload, status_code=200):
        self._p = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_content(self, chunk_size=0):
        yield b"dropbox-file-bytes"


class _FakeDropboxSession:
    def __init__(self):
        self.headers = {}
        self.posts = []
        self._entries = [
            {
                ".tag": "folder",
                "name": "config",
                "path_display": "/.image-toolkit/config",
            },
            {
                ".tag": "file",
                "name": "theme.qss",
                "path_display": "/.image-toolkit/theme.qss",
                "server_modified": "2026-08-31T18:00:00Z",
                "size": 128,
            },
            {
                ".tag": "file",
                "name": "settings.json",
                "path_display": "/.image-toolkit/config/settings.json",
                "server_modified": "2026-08-31T18:05:00Z",
                "size": 256,
            },
        ]

    def post(self, url, timeout=None, json=None, data=None, headers=None, stream=False, **kw):
        self.posts.append((url, json, data, headers))
        if "files/list_folder" in url:
            if "continue" in url:
                return _Resp({"entries": [], "has_more": False})
            return _Resp({"entries": self._entries, "cursor": "cur123", "has_more": False})
        if "files/upload" in url:
            return _Resp({"name": "uploaded", "size": 100})
        if "files/download" in url:
            arg = (headers or {}).get("Dropbox-API-Arg", "{}")
            path = json_loads(arg).get("path", "")
            if "nonexistent" in path:
                return _Resp({}, status_code=409)
            return _Resp({})
        if "files/create_folder_v2" in url:
            return _Resp({"metadata": {"name": "created"}})
        return _Resp({})


def json_loads(s):
    try:
        return json.loads(s)
    except Exception:
        return {}


@pytest.fixture
def client(monkeypatch):
    fake = _FakeDropboxSession()
    monkeypatch.setattr(
        "backend.src.web.cloud.dropbox_file_client.requests.Session", lambda: fake
    )
    c = DropboxFileClient("tok-123", root_name=".image-toolkit", logger=lambda *_: None)
    c._fake = fake
    return c


def test_init_validation():
    with pytest.raises(ValueError, match="needs a valid access_token"):
        DropboxFileClient("")


def test_list_remote_files_maps_relative_paths(client):
    files = client.list_remote_files()
    got = {f["path"]: f for f in files}

    assert "theme.qss" in got
    assert "config/settings.json" in got
    assert got["theme.qss"]["size"] == 128
    assert got["config/settings.json"]["size"] == 256
    assert got["theme.qss"]["mtime"] > 0


def test_upload_file_posts_content_and_headers(client, tmp_path):
    p = tmp_path / "test.txt"
    p.write_bytes(b"content")

    client.upload_file(str(p), "config/test.txt")

    urls = [url for url, *_ in client._fake.posts]
    assert any("files/upload" in u for u in urls)
    upload_call = [call for call in client._fake.posts if "files/upload" in call[0]][0]
    headers = upload_call[3]
    api_arg = json.loads(headers["Dropbox-API-Arg"])
    assert api_arg["path"] == "/.image-toolkit/config/test.txt"
    assert api_arg["mode"] == "overwrite"


def test_download_file_writes_local(client, tmp_path):
    out = tmp_path / "downloaded" / "theme.qss"
    client.download_file("theme.qss", str(out))

    assert out.exists()
    assert out.read_bytes() == b"dropbox-file-bytes"


def test_download_file_missing_raises_filenotfound(client, tmp_path):
    out = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError, match="remote file not found"):
        client.download_file("nonexistent.txt", str(out))
