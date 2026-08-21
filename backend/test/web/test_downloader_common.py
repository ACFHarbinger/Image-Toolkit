"""Tests for the shared downloader helpers (retry + existing-file policy)."""

from __future__ import annotations

from backend.src.web.downloaders._common import (
    ON_EXISTS_OVERWRITE,
    ON_EXISTS_RENAME,
    ON_EXISTS_SKIP,
    is_retryable_status,
    resolve_dest_path,
)


class TestIsRetryableStatus:
    def test_rate_limit_and_5xx_retryable(self):
        for status in (429, 500, 502, 503, 504):
            assert is_retryable_status(status) is True

    def test_4xx_and_success_not_retryable(self):
        for status in (200, 400, 403, 404, 410):
            assert is_retryable_status(status) is False


class TestResolveDestPath:
    def test_no_existing_file_returns_dest_for_all_policies(self, tmp_path):
        dest = str(tmp_path / "img.jpg")
        for policy in (ON_EXISTS_OVERWRITE, ON_EXISTS_SKIP, ON_EXISTS_RENAME):
            assert resolve_dest_path(dest, policy) == dest

    def test_overwrite_returns_same_path(self, tmp_path):
        dest = tmp_path / "img.jpg"
        dest.write_bytes(b"x")
        assert resolve_dest_path(str(dest), ON_EXISTS_OVERWRITE) == str(dest)

    def test_skip_returns_none_when_exists(self, tmp_path):
        dest = tmp_path / "img.jpg"
        dest.write_bytes(b"x")
        assert resolve_dest_path(str(dest), ON_EXISTS_SKIP) is None

    def test_rename_counts_existing_files(self, tmp_path):
        dest = tmp_path / "img.jpg"
        dest.write_bytes(b"x")
        (tmp_path / "img(1).jpg").write_bytes(b"x")
        (tmp_path / "img(2).jpg").write_bytes(b"x")
        assert resolve_dest_path(str(dest), ON_EXISTS_RENAME) == str(tmp_path / "img(3).jpg")

    def test_rename_keeps_extension(self, tmp_path):
        dest = tmp_path / "page.png"
        dest.write_bytes(b"x")
        assert resolve_dest_path(str(dest), ON_EXISTS_RENAME) == str(tmp_path / "page(1).png")
