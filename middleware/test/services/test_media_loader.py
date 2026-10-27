from __future__ import annotations

from middleware.src.services.media_loader.plan import plan_download


def test_plan_accepts_an_existing_directory_without_downloading(tmp_path) -> None:
    url = "https://example.com/a.png"
    result = plan_download(url, str(tmp_path))
    assert result["accepted"] is True
    assert result["downloaded"] is False
    assert result["reason"] == "download is not performed"
    assert result["url"] == url
    assert list(tmp_path.iterdir()) == []


def test_plan_rejects_bad_urls_and_missing_directories(tmp_path) -> None:
    missing = str(tmp_path / "missing")
    assert plan_download("file:///tmp/a.png", missing)["reason"] == "url must be http or https"
    assert plan_download("https://user:secret@example.com/a", missing)["reason"] == "url must not carry credentials"
    assert plan_download("https://example.com/a.png", missing)["reason"] == "destination directory is missing"


def test_fetch_media_success(tmp_path, monkeypatch) -> None:
    from middleware.src.services.media_loader.fetch import fetch_media
    from middleware.src.sidecar.handlers.media_loader import handle_media_fetch

    class DummyResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, chunk_size=-1):
            if not hasattr(self, "_read"):
                self._read = True
                return b"fake image bytes"
            return b""
        def getheader(self, name, default=None):
            return "image/png"

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: DummyResponse())

    out_file = tmp_path / "test.png"
    result = fetch_media("https://example.com/test.png", str(tmp_path))
    assert result["success"] is True
    assert result["destination_path"] == str(out_file)
    assert result["bytes_downloaded"] == len(b"fake image bytes")
    assert out_file.read_bytes() == b"fake image bytes"

    handler_result = handle_media_fetch({
        "url": "https://example.com/test.png",
        "destination": str(tmp_path),
    })
    assert handler_result["success"] is True
    assert handler_result["destination_path"] == str(out_file)


def test_fetch_failure_keeps_an_existing_file(tmp_path, monkeypatch) -> None:
    from middleware.src.services.media_loader.fetch import fetch_media

    existing = tmp_path / "test.png"
    existing.write_bytes(b"keep-me")

    def boom(*_args, **_kwargs):
        raise OSError("connection failed")

    monkeypatch.setattr("middleware.src.services.media_loader.fetch.urllib.request.urlopen", boom)
    result = fetch_media("https://example.com/test.png", str(tmp_path))
    assert result["success"] is False
    assert existing.read_bytes() == b"keep-me"
    assert list(tmp_path.glob(".test.png.*")) == []

