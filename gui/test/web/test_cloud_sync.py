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
            allowlist=(),  # Disable allowlist for test
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
            allowlist=(),  # Disable allowlist for test
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
            allowlist=(),  # Disable allowlist for test
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
            allowlist=(),  # Disable allowlist for test
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
            allowlist=(),  # Disable allowlist for test
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
            allowlist=(),  # Disable allowlist for test
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
            allowlist=(),  # Disable allowlist for test
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
            allowlist=(),  # Disable allowlist for test — only denylist matters here
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


class TestLocalDirSyncAllowlist:
    """Tests for the allowlist feature (#482 S1)."""

    def test_allowlist_filters_non_matching_files(self, tmp_path: Path):
        """Files not in the allowlist should be skipped."""
        # Create files that match and don't match the allowlist
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "settings.json").write_text('{"theme": "dark"}')

        # This file is NOT in the default allowlist
        (tmp_path / "random_file.txt").write_text("not synced")

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={},
            # Use default allowlist
        )
        plan = engine.build_plan()

        upload_paths = [u.relpath for u in plan.uploads]
        assert "config/settings.json" in upload_paths
        assert "random_file.txt" not in upload_paths

    def test_empty_allowlist_allows_all(self, tmp_path: Path):
        """An empty allowlist should allow all files (minus excludes)."""
        (tmp_path / "any_file.txt").write_text("content")
        (tmp_path / "another.dat").write_bytes(b"data")

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={},
            allowlist=(),  # Empty = allow all
        )
        plan = engine.build_plan()

        upload_paths = [u.relpath for u in plan.uploads]
        assert "any_file.txt" in upload_paths
        assert "another.dat" in upload_paths

    def test_allowlist_with_directory_pattern(self, tmp_path: Path):
        """Directory patterns in allowlist should match contents."""
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "image.png").write_bytes(b"png data")
        (assets_dir / "subdir").mkdir()
        (assets_dir / "subdir" / "nested.txt").write_text("nested")

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={},
            allowlist=("assets/",),
        )
        plan = engine.build_plan()

        upload_paths = [u.relpath for u in plan.uploads]
        assert "assets/image.png" in upload_paths
        assert "assets/subdir/nested.txt" in upload_paths

    def test_denylist_still_blocks_allowlisted_files(self, tmp_path: Path):
        """Files matching the denylist should be excluded even if in allowlist."""
        # Create a file that would match allowlist but also matches denylist
        secrets_dir = tmp_path / "config"
        secrets_dir.mkdir()
        (secrets_dir / "secret.vault").write_bytes(b"encrypted")
        (secrets_dir / "normal.json").write_text('{"ok": true}')

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={},
            allowlist=("config/",),
            excludes=DEFAULT_EXCLUDES,
        )
        plan = engine.build_plan()

        upload_paths = [u.relpath for u in plan.uploads]
        assert "config/normal.json" in upload_paths
        assert "config/secret.vault" not in upload_paths  # Blocked by denylist


class TestLocalDirSyncContentHash:
    """Tests for content-hash tie-break (#482 S4)."""

    def test_content_hash_verifies_identical_files(self, tmp_path: Path):
        """Files with same size+mtime but different content should be detected."""
        f = tmp_path / "data.txt"
        f.write_text("version 1")
        st = f.stat()

        # Remote has same size and mtime, but claims different content_hash
        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={
                "data.txt": {
                    "mtime": st.st_mtime,
                    "size": st.st_size,
                    "content_hash": "different_hash_value",
                }
            },
            allowlist=(),
        )
        plan = engine.build_plan()

        # Should be a conflict since hashes differ
        assert len(plan.conflicts) + len(plan.uploads) + len(plan.downloads) >= 1

    def test_content_hash_matches_skips_sync(self, tmp_path: Path):
        """Files with matching content hashes should be skipped."""
        f = tmp_path / "data.txt"
        f.write_text("identical content")
        st = f.stat()

        # Compute the actual hash
        import hashlib

        expected_hash = hashlib.sha256(b"identical content").hexdigest()

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={
                "data.txt": {
                    "mtime": st.st_mtime,
                    "size": st.st_size,
                    "content_hash": expected_hash,
                }
            },
            allowlist=(),
        )
        plan = engine.build_plan()

        # Should be skipped since content matches
        assert len(plan.skipped) == 1
        assert plan.skipped[0].relpath == "data.txt"
        assert "verified" in plan.skipped[0].reason


class TestLocalDirSyncCancellation:
    """Tests for cancellation checks in build_plan (#482 S4)."""

    def test_cancellation_during_local_files(self, tmp_path: Path):
        """build_plan should respect cancellation during _local_files."""
        # Create many files to trigger cancellation check
        for i in range(150):
            (tmp_path / f"file_{i}.txt").write_text(f"content {i}")

        cancel_count = [0]

        def cancel_after_50():
            cancel_count[0] += 1
            return cancel_count[0] > 1  # Cancel after first check

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={},
            allowlist=(),
            cancelled_check=cancel_after_50,
        )
        plan = engine.build_plan()

        # Should have stopped early due to cancellation
        # (not all 150 files should be in the plan)
        assert len(plan.uploads) < 150

    def test_cancellation_during_build_plan(self, tmp_path: Path):
        """build_plan should respect cancellation during path iteration."""
        # Create files
        for i in range(150):
            (tmp_path / f"file_{i}.txt").write_text(f"content {i}")

        call_count = [0]

        def cancel_check():
            call_count[0] += 1
            return False  # Never actually cancel, just count calls

        engine = LocalDirSyncEngine(
            local_root=tmp_path,
            remote_listing={},
            allowlist=(),
            cancelled_check=cancel_check,
        )
        engine.build_plan()

        # Cancellation check should have been called during build_plan
        # (at least once for the path iteration, plus calls from _local_files)
        assert call_count[0] > 0


class TestLocalDirSyncSignalsRemoved:
    """Verify dead LocalDirSyncSignals class is removed (#482 S4)."""

    def test_no_local_dir_sync_signals_class(self):
        """LocalDirSyncSignals should not exist in the module."""
        from gui.src.helpers.web.cloud import local_dir_sync_worker

        assert not hasattr(local_dir_sync_worker, "LocalDirSyncSignals")


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

        subtab.set_config(
            {
                "local_path": "/tmp/custom_sync",
                "remote_path": "CloudBackups",
                "dry_run": False,
                "action_local_orphans": "delete_local",
            }
        )
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

        subtab.set_config(
            {
                "local_path": "/tmp/custom_app_dir",
                "remote_folder": ".itk-remote",
                "conflict_policy": ConflictPolicy.PREFER_LOCAL.value,
                "dry_run": False,
            }
        )
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
