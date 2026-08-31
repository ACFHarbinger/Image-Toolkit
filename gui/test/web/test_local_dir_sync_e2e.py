"""#479 e2e path for Local Directory Sync: exclude list + worker dry-run/live.

Live Google Drive is optional — set ``IT_GDRIVE_ACCESS_TOKEN`` to a Drive
v3 OAuth/service-account access token to hit a uniquely-named remote
folder (``.itk-e2e-479-<pid>``). Without it, the FakeDrive path still
proves the worker never hands excluded files to ``upload_file``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from gui.src.helpers.web.cloud.local_dir_sync_worker import (
    DEFAULT_EXCLUDES,
    LocalDirSyncEngine,
    LocalDirSyncWorker,
)

_LIVE_TOKEN = os.environ.get("IT_GDRIVE_ACCESS_TOKEN", "").strip()

_FORBIDDEN_SUFFIXES = (".vault", ".p12", ".pfx", ".pem", ".key")
_FORBIDDEN_NAMES = {
    "library.db",
    "library.db-wal",
    "library.db-shm",
    "listings_secure.db",
    ".slideshow_config.json",
}
_ALLOWED = {"theme.qss", "config/ui.json"}


def _scratch_itk_tree(root: Path) -> None:
    """A ~/.image-toolkit-shaped tree: secrets + one allowed config pair."""
    (root / "config").mkdir()
    (root / "config" / "ui.json").write_text('{"theme":"dark"}')
    (root / "theme.qss").write_text("QWidget { color: #ccc; }")

    (root / "keystore.vault").write_bytes(b"encrypted-vault")
    (root / "app.p12").write_bytes(b"pkcs12")
    (root / "library.db").write_bytes(b"sqlcipher")
    (root / "library.db-wal").write_bytes(b"wal")
    (root / "library.db-shm").write_bytes(b"shm")
    (root / "listings_secure.db").write_bytes(b"listings")
    (root / ".slideshow_config.json").write_text("{}")

    (root / "cryptography").mkdir()
    (root / "cryptography" / "my_secure_data-a.vault").write_bytes(b"key-material")
    (root / "secrets").mkdir()
    (root / "secrets" / "token.json").write_text("secret")
    (root / "logs").mkdir()
    (root / "logs" / "app.log").write_text("/home/pkhunter/leaked-path")
    (root / "telemetry").mkdir()
    (root / "telemetry" / "events.json").write_text("{}")
    (root / "thumbnail-cache").mkdir()
    (root / "thumbnail-cache" / "a.png").write_bytes(b"png")


def _assert_no_forbidden(paths: list[str]) -> None:
    for p in paths:
        name = Path(p).name
        assert name not in _FORBIDDEN_NAMES, p
        assert not name.endswith(_FORBIDDEN_SUFFIXES), p
        parts = Path(p).parts
        assert "cryptography" not in parts and "secrets" not in parts
        assert "logs" not in parts and "telemetry" not in parts
        assert "thumbnail-cache" not in parts


class _FakeDrive:
    """In-memory stand-in for GoogleDriveFileClient's worker interface."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.uploaded: list[str] = []
        self.downloaded: list[str] = []

    def list_remote_files(self) -> list[dict]:
        return [
            {"path": p, "mtime": 1.0, "size": len(b)} for p, b in self.store.items()
        ]

    def upload_file(self, local_abs: str, relpath: str) -> None:
        self.uploaded.append(relpath)
        self.store[relpath] = Path(local_abs).read_bytes()

    def download_file(self, relpath: str, local_abs: str) -> None:
        self.downloaded.append(relpath)
        Path(local_abs).parent.mkdir(parents=True, exist_ok=True)
        Path(local_abs).write_bytes(self.store[relpath])


def test_engine_excludes_db_and_key_material(tmp_path: Path):
    root = tmp_path / "itk"
    root.mkdir()
    _scratch_itk_tree(root)
    plan = LocalDirSyncEngine(
        local_root=root,
        remote_listing={
            "remote.vault": {"mtime": 1.0, "size": 4},
            "library.db": {"mtime": 1.0, "size": 4},
        },
        excludes=DEFAULT_EXCLUDES,
    ).build_plan()
    uploads = [u.relpath for u in plan.uploads]
    downloads = [d.relpath for d in plan.downloads]
    assert set(uploads) == _ALLOWED
    _assert_no_forbidden(uploads)
    _assert_no_forbidden(downloads)
    assert "library.db" not in downloads
    assert "remote.vault" not in downloads


def test_worker_dry_run_does_not_upload(q_app, tmp_path: Path):
    root = tmp_path / "itk"
    root.mkdir()
    _scratch_itk_tree(root)
    fake = _FakeDrive()
    worker = LocalDirSyncWorker(
        auth_config={},
        provider_text="Google Drive (Service Account)",
        local_root=root,
        remote_folder=".itk-e2e",
        dry_run=True,
    )
    worker._client = fake
    worker._execute()
    assert fake.uploaded == []
    assert fake.store == {}


def test_worker_live_uploads_only_allowed_files(q_app, tmp_path: Path):
    root = tmp_path / "itk"
    root.mkdir()
    _scratch_itk_tree(root)
    fake = _FakeDrive()
    worker = LocalDirSyncWorker(
        auth_config={},
        provider_text="Google Drive (Service Account)",
        local_root=root,
        remote_folder=".itk-e2e",
        dry_run=False,
    )
    worker._client = fake
    worker._execute()
    assert set(fake.uploaded) == _ALLOWED
    _assert_no_forbidden(fake.uploaded)
    _assert_no_forbidden(list(fake.store))
    assert fake.store["theme.qss"].startswith(b"QWidget")


@pytest.mark.skipif(not _LIVE_TOKEN, reason="IT_GDRIVE_ACCESS_TOKEN not set")
def test_live_gdrive_dry_run_then_sync_excludes_secrets(q_app, tmp_path: Path):
    from backend.src.web.cloud.gdrive_file_client import GoogleDriveFileClient

    root = tmp_path / "itk"
    root.mkdir()
    _scratch_itk_tree(root)
    folder = f".itk-e2e-479-{os.getpid()}"
    client = GoogleDriveFileClient(_LIVE_TOKEN, root_name=folder)
    worker = LocalDirSyncWorker(
        auth_config={},
        provider_text="Google Drive (Service Account)",
        local_root=root,
        remote_folder=folder,
        dry_run=True,
    )
    worker._client = client
    worker._execute()
    listing_after_dry = {i["path"] for i in client.list_remote_files()}
    assert listing_after_dry == set()

    worker.dry_run = False
    worker._execute()
    listing = {i["path"] for i in client.list_remote_files()}
    assert listing >= _ALLOWED
    _assert_no_forbidden(list(listing))
