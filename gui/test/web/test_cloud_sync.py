"""Unit tests for Cloud Sync tab restructure and Local Directory Sync (issue #479)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gui.src.helpers.web.cloud.local_dir_sync_worker import (
    DEFAULT_EXCLUDES,
    ConflictPolicy,
    LocalDirSyncEngine,
    LocalDirSyncWorker,
)
from gui.src.tabs.web.drive_sync_tab import DriveSyncTab
from gui.src.tabs.web.drive_sync_tab.local_dir_sync_subtab import LocalDirSyncSubtab
from gui.src.tabs.web.drive_sync_tab.sync_data_subtab import SyncDataSubtab


class TestLocalDirSyncEngine:
    """Pure logic tests for diffing and conflict resolution without network."""

    def test_new_local_file_triggers_upload(self, tmp_path: Path):
        test_file = tmp_path / "config.json"
        test_file.write_text('{"theme": "dark"}')

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={},
        )
        plan = engine.build_plan()

        assert len(plan.uploads) == 1
        assert plan.uploads[0].relpath == "config.json"
        assert plan.uploads[0].action == "upload"
        assert len(plan.downloads) == 0

    def test_new_remote_file_triggers_download(self, tmp_path: Path):
        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={"styles/custom.qss": {"mtime": 1000.0, "size": 256}},
        )
        plan = engine.build_plan()

        assert len(plan.downloads) == 1
        assert plan.downloads[0].relpath == "styles/custom.qss"
        assert plan.downloads[0].action == "download"
        assert len(plan.uploads) == 0

    def test_identical_file_is_skipped(self, tmp_path: Path):
        f = tmp_path / "preset.yaml"
        f.write_text("model: anime")
        st = f.stat()

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={"preset.yaml": {"mtime": st.st_mtime, "size": st.st_size}},
        )
        plan = engine.build_plan()

        assert len(plan.uploads) == 0
        assert len(plan.downloads) == 0
        assert len(plan.skipped) == 1
        assert plan.skipped[0].relpath == "preset.yaml"

    def test_conflict_newer_wins_local_newer(self, tmp_path: Path):
        f = tmp_path / "state.json"
        f.write_text("v2")
        st = f.stat()

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={"state.json": {"mtime": st.st_mtime - 100.0, "size": 10}},
            conflict_policy=ConflictPolicy.NEWER_WINS,
        )
        plan = engine.build_plan()

        assert len(plan.uploads) == 1
        assert plan.uploads[0].relpath == "state.json"
        assert plan.uploads[0].action == "upload"

    def test_conflict_newer_wins_remote_newer(self, tmp_path: Path):
        f = tmp_path / "state.json"
        f.write_text("v1")
        st = f.stat()

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={"state.json": {"mtime": st.st_mtime + 100.0, "size": 50}},
            conflict_policy=ConflictPolicy.NEWER_WINS,
        )
        plan = engine.build_plan()

        assert len(plan.downloads) == 1
        assert plan.downloads[0].relpath == "state.json"
        assert plan.downloads[0].action == "download"

    def test_conflict_prefer_local(self, tmp_path: Path):
        f = tmp_path / "state.json"
        f.write_text("local")
        st = f.stat()

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={"state.json": {"mtime": st.st_mtime + 500.0, "size": 999}},
            conflict_policy=ConflictPolicy.PREFER_LOCAL,
        )
        plan = engine.build_plan()

        assert len(plan.uploads) == 1
        assert plan.uploads[0].relpath == "state.json"

    def test_conflict_prefer_remote(self, tmp_path: Path):
        f = tmp_path / "state.json"
        f.write_text("local")
        st = f.stat()

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={"state.json": {"mtime": st.st_mtime - 500.0, "size": 5}},
            conflict_policy=ConflictPolicy.PREFER_REMOTE,
        )
        plan = engine.build_plan()

        assert len(plan.downloads) == 1
        assert plan.downloads[0].relpath == "state.json"

    def test_exclude_list_security_enforcement(self, tmp_path: Path):
        """Confirm sensitive files are excluded and never planned for sync."""
        (tmp_path / "keystore.vault").write_bytes(b"encrypted_secret")
        (tmp_path / "app.p12").write_bytes(b"cert")
        (tmp_path / "private.key").write_bytes(b"key")
        (tmp_path / "run.log").write_text("/home/user/path/leak")
        (tmp_path / "trace.trace").write_text("trace data")

        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "token.json").write_text("token")

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "crash.log").write_text("crash info")

        cache_dir = tmp_path / "thumbnail-cache"
        cache_dir.mkdir()
        (cache_dir / "thumb1.png").write_bytes(b"png")

        # Non-sensitive file
        (tmp_path / "theme.qss").write_text("QWidget { color: red; }")

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={
                "remote.vault": {"mtime": 1.0, "size": 10},
                "remote.log": {"mtime": 1.0, "size": 10},
            },
            excludes=DEFAULT_EXCLUDES,
        )
        plan = engine.build_plan()

        # Only theme.qss should be in uploads
        upload_paths = [u.relpath for u in plan.uploads]
        assert upload_paths == ["theme.qss"]

        # No sensitive files in downloads
        download_paths = [d.relpath for d in plan.downloads]
        assert "remote.vault" not in download_paths
        assert "remote.log" not in download_paths


class TestSubtabWidgets:
    @pytest.fixture
    def mock_vault(self):
        vault = MagicMock()
        vault.api_credentials = {"image_toolkit_service": {"test": "val"}}
        return vault

    def test_sync_data_subtab_config(self, q_app):
        subtab = SyncDataSubtab(
            get_auth_config=lambda: {"mode": "test"},
            get_provider_text=lambda: "Google Drive (Personal Account)",
        )
        cfg = subtab.collect()
        assert "local_path" in cfg
        assert "remote_path" in cfg
        assert "dry_run" in cfg

        subtab.set_config({
            "local_path": "/tmp/custom_sync",
            "remote_path": "CloudBackups",
            "dry_run": False,
            "action_local_orphans": "delete_local",
        })
        new_cfg = subtab.collect()
        assert new_cfg["local_path"] == "/tmp/custom_sync"
        assert new_cfg["remote_path"] == "CloudBackups"
        assert new_cfg["dry_run"] is False
        assert new_cfg["action_local_orphans"] == "delete_local"

    def test_local_dir_sync_subtab_config(self, q_app):
        subtab = LocalDirSyncSubtab(
            get_auth_config=lambda: {"mode": "test"},
            get_provider_text=lambda: "Google Drive (Personal Account)",
        )
        cfg = subtab.collect()
        assert "local_path" in cfg
        assert "remote_folder" in cfg
        assert "conflict_policy" in cfg
        assert "excludes" in cfg

        subtab.set_config({
            "local_path": "/tmp/custom_app_dir",
            "remote_folder": ".itk-remote",
            "conflict_policy": ConflictPolicy.PREFER_LOCAL.value,
            "dry_run": False,
        })
        new_cfg = subtab.collect()
        assert new_cfg["local_path"] == "/tmp/custom_app_dir"
        assert new_cfg["remote_folder"] == ".itk-remote"
        assert new_cfg["conflict_policy"] == ConflictPolicy.PREFER_LOCAL.value
        assert new_cfg["dry_run"] is False

    def test_drive_sync_tab_container(self, q_app, mock_vault):
        tab = DriveSyncTab(mock_vault)
        assert tab.subtab_widget.count() == 2
        assert tab.subtab_widget.tabText(0) == "Sync Data"
        assert tab.subtab_widget.tabText(1) == "Local Directory Sync"

        cfg = tab.collect()
        assert "sync_data" in cfg
        assert "local_dir_sync" in cfg
        assert "provider" in cfg

    def test_worker_cancellation(self, tmp_path: Path):
        worker = LocalDirSyncWorker(
            auth_config={"mode": "test"},
            provider_text="Dropbox",
            local_root=tmp_path,
            remote_folder=".test",
            dry_run=True,
        )
        assert not worker._cancelled
        worker.stop()
        assert worker._cancelled
