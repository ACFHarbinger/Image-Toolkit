"""GoogleDriveFileClient — path-addressed Drive v3 ops, fully mocked HTTP."""

from __future__ import annotations

import pytest

from backend.src.web.cloud.gdrive_file_client import GoogleDriveFileClient


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        ...

    def json(self):
        return self._p

    # download context-manager + streaming
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_content(self, chunk_size=0):
        yield b"payload-bytes"


class _FakeSession:
    """Emulates just enough of a Drive v3 tree: root '.image-toolkit' with
    sub 'config/settings.json' and top-level 'theme.qss'."""

    def __init__(self):
        self.headers = {}
        self.posts = []
        self._files = {
            "root-id": [
                {"id": "cfg-id", "name": "config", "mimeType": "application/vnd.google-apps.folder"},
                {"id": "qss-id", "name": "theme.qss", "mimeType": "text/plain",
                 "modifiedTime": "2026-08-31T18:00:00Z", "size": "12"},
            ],
            "cfg-id": [
                {"id": "set-id", "name": "settings.json", "mimeType": "application/json",
                 "modifiedTime": "2026-08-31T18:05:00Z", "size": "34"},
            ],
        }

    def get(self, url, timeout=None, params=None, **kw):
        q = (params or {}).get("q", "")
        if "alt" in (params or {}):
            return _Resp({})  # download
        if "'root' in parents" in q and ".image-toolkit" in q:
            return _Resp({"files": [{"id": "root-id", "name": ".image-toolkit",
                                     "mimeType": "application/vnd.google-apps.folder"}]})
        for parent, kids in self._files.items():
            if f"'{parent}' in parents" in q:
                # optional name filter
                if "name = '" in q:
                    want = q.split("name = '", 1)[1].split("'", 1)[0]
                    kids = [k for k in kids if k["name"] == want]
                return _Resp({"files": kids})
        return _Resp({"files": []})

    def post(self, url, timeout=None, json=None, files=None, **kw):
        self.posts.append(("POST", url, json, files))
        return _Resp({"id": "new-id"})

    def patch(self, url, timeout=None, files=None, **kw):
        self.posts.append(("PATCH", url, None, files))
        return _Resp({"id": "patched"})


@pytest.fixture
def client(monkeypatch):
    fake = _FakeSession()
    monkeypatch.setattr(
        "backend.src.web.cloud.gdrive_file_client.requests.Session", lambda: fake
    )
    c = GoogleDriveFileClient("tok", root_name=".image-toolkit", logger=lambda *_: None)
    c._fake = fake
    return c


def test_list_remote_files_maps_nested_paths(client):
    got = {f["path"]: f for f in client.list_remote_files()}
    assert set(got) == {"theme.qss", "config/settings.json"}
    assert got["config/settings.json"]["size"] == 34
    assert got["theme.qss"]["mtime"] > 0


def test_upload_new_file_creates_parents_and_POSTs(client, tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{}")
    client.upload_file(str(p), "config/new/x.json")
    methods = [m for m, *_ in client._fake.posts]
    assert "POST" in methods  # the file create
    # a folder 'new' had to be created under 'config'
    folder_posts = [j for m, u, j, f in client._fake.posts if j and j.get("mimeType", "").endswith("folder")]
    assert any(j["name"] == "new" for j in folder_posts)


def test_upload_existing_file_PATCHes(client, tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{}")
    client.upload_file(str(p), "config/settings.json")
    assert client._fake.posts[-1][0] == "PATCH"


def test_ensure_folder_is_cached(client):
    a = client.ensure_folder("config")
    n_posts = len(client._fake.posts)
    b = client.ensure_folder("config")
    assert a == b and len(client._fake.posts) == n_posts


def test_download_missing_raises(client):
    with pytest.raises(FileNotFoundError):
        client.download_file("config/nope.txt", "/tmp/nope.txt")
