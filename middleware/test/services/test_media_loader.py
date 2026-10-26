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
