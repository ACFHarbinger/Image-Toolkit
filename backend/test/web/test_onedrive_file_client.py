"""OneDriveFileClient — path-addressed Microsoft Graph ops, fully mocked HTTP."""

from __future__ import annotations

import pytest

from backend.src.web.cloud.onedrive_file_client import OneDriveFileClient


class _Resp:
    def __init__(self, payload, status_code=200):
        self._p = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._p

    def iter_content(self, chunk_size=0):
        yield b"onedrive-file-bytes"


class _FakeSession:
    """Emulates just enough of an MS Graph OneDrive tree: root
    '.image-toolkit' has a 'config' folder (with 'settings.json') and a
    top-level 'theme.qss' file."""

    def __init__(self):
        self.headers = {}
        self.calls = []

    def get(self, url, timeout=None, stream=False, **kw):
        self.calls.append(("GET", url, None, None))
        if "nonexistent" in url:
            return _Resp({}, status_code=404)
        if "/content" in url:
            return _Resp({})
        if url.endswith("/root:/.image-toolkit:/children"):
            return _Resp({
                "value": [
                    {"id": "cfg", "name": "config", "folder": {},
                     "lastModifiedDateTime": "2026-08-31T18:00:00Z"},
                    {"id": "qss", "name": "theme.qss",
                     "file": {"size": 128},
                     "lastModifiedDateTime": "2026-08-31T18:01:00Z"},
                ]
            })
        if url.endswith("/root:/.image-toolkit/config:/children"):
            return _Resp({
                "value": [
                    {"id": "set", "name": "settings.json",
                     "file": {"size": 256},
                     "lastModifiedDateTime": "2026-08-31T18:05:00Z"},
                ]
            })
        if url.rstrip("/").endswith(":"):
            # folder-existence metadata probe
            return _Resp({"id": "x", "name": "x", "folder": {}})
        return _Resp({"value": []})

    def post(self, url, timeout=None, json=None, **kw):
        self.calls.append(("POST", url, json, None))
        return _Resp({"id": "new-folder"})

    def put(self, url, timeout=None, data=None, **kw):
        self.calls.append(("PUT", url, None, data))
        return _Resp({"id": "uploaded"})


@pytest.fixture
def client(monkeypatch):
    fake = _FakeSession()
    monkeypatch.setattr(
        "backend.src.web.cloud.onedrive_file_client.requests.Session", lambda: fake
    )
    c = OneDriveFileClient("tok-123", root_name=".image-toolkit", logger=lambda *_: None)
    c._fake = fake
    return c


def test_init_validation():
    with pytest.raises(ValueError, match="needs a valid access_token"):
        OneDriveFileClient("")


def test_list_remote_files_maps_nested_paths(client):
    got = {f["path"]: f for f in client.list_remote_files()}
    assert set(got) == {"theme.qss", "config/settings.json"}
    assert got["theme.qss"]["size"] == 128
    assert got["config/settings.json"]["size"] == 256
    assert got["theme.qss"]["mtime"] > 0


def test_upload_file_puts_content_to_content_endpoint(client, tmp_path):
    p = tmp_path / "test.txt"
    p.write_bytes(b"hello")
    client.upload_file(str(p), "config/test.txt")

    methods = [m for m, *_ in client._fake.calls]
    assert "PUT" in methods
    put_call = [c for c in client._fake.calls if c[0] == "PUT"][0]
    assert put_call[1].endswith("/root:/.image-toolkit/config/test.txt:/content")


def test_download_file_writes_local(client, tmp_path):
    out = tmp_path / "downloaded" / "theme.qss"
    client.download_file("theme.qss", str(out))

    assert out.exists()
    assert out.read_bytes() == b"onedrive-file-bytes"


def test_download_file_missing_raises_filenotfound(client, tmp_path):
    out = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError, match="remote file not found"):
        client.download_file("nonexistent.txt", str(out))
