"""Unit tests for PostgreSQL prerequisite check and diagnostics (issue #477)."""

from __future__ import annotations

from unittest.mock import patch

from gui.src.helpers.database.postgres_check import (
    PostgresStatus,
    check_postgres_reachability,
    load_postgres_config,
    show_postgres_status_dialog,
)


class TestPostgresCheck:
    def test_load_postgres_config_from_env(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@dbhost:5432/itk")
        cfg = load_postgres_config()
        assert cfg.get("DATABASE_URL") == "postgresql://user:pass@dbhost:5432/itk"

    def test_load_postgres_config_postgres_prefix(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_DB", "custom_db")
        monkeypatch.setenv("POSTGRES_USER", "custom_user")
        monkeypatch.setenv("POSTGRES_HOST", "192.168.1.100")
        monkeypatch.setenv("POSTGRES_PORT", "5433")

        cfg = load_postgres_config()
        assert cfg.get("DB_NAME") == "custom_db"
        assert cfg.get("DB_USER") == "custom_user"
        assert cfg.get("DB_HOST") == "192.168.1.100"
        assert cfg.get("DB_PORT") == "5433"

    def test_reachability_handles_unreachable_server_gracefully(self, monkeypatch):
        # Point to a non-existent port with immediate timeout
        monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
        monkeypatch.setenv("POSTGRES_PORT", "65432")

        status = check_postgres_reachability(timeout=1)
        assert isinstance(status, PostgresStatus)
        assert status.reachable is False
        assert status.has_pgvector is False
        assert "Could not connect" in status.message or "driver" in status.message

    def test_show_postgres_status_dialog_offline(self, q_app):
        with (
            patch("gui.src.helpers.database.postgres_check.check_postgres_reachability") as mock_check,
            patch("gui.src.helpers.database.postgres_check.QMessageBox.information") as mock_info,
        ):
            mock_check.return_value = PostgresStatus(
                reachable=False,
                has_pgvector=False,
                version_str="",
                message="Offline",
            )
            status = show_postgres_status_dialog(parent=None)
            assert status.reachable is False
            mock_info.assert_called_once()
            args, _ = mock_info.call_args
            assert "PostgreSQL Offline" in args[1]
            assert "INSTALL.md" in args[2]

    def test_show_postgres_status_dialog_missing_vector(self, q_app):
        with (
            patch("gui.src.helpers.database.postgres_check.check_postgres_reachability") as mock_check,
            patch("gui.src.helpers.database.postgres_check.QMessageBox.warning") as mock_warn,
        ):
            mock_check.return_value = PostgresStatus(
                reachable=True,
                has_pgvector=False,
                version_str="PostgreSQL 16.1",
                message="Missing extension",
            )
            status = show_postgres_status_dialog(parent=None)
            assert status.reachable is True
            assert status.has_pgvector is False
            mock_warn.assert_called_once()
            args, _ = mock_warn.call_args
            assert "pgvector Extension Missing" in args[1]
            assert "just db-setup" in args[2]
