"""Tests for DB.8d's directory-import batching (issue #66):
gui/src/tabs/core/elements/series_listings_subtab/_directory_import.py --
the whole batch of newly-created series commits in a single transaction,
and a series whose name matches an existing image group gets that
media_groups link pre-filled.
"""

from unittest.mock import MagicMock, patch

import pytest
from gui.src.tabs.database.series_listings_subtab import SeriesListingsSubTab
from PySide6.QtWidgets import QDialog

pytestmark = pytest.mark.gui


def _make_tab():
    return SeriesListingsSubTab(vault_manager=None)


def _mock_dialog(selected_series, scan_result, metadata=None):
    dlg = MagicMock()
    dlg.exec.return_value = QDialog.DialogCode.Accepted
    dlg.get_selected_series.return_value = selected_series
    dlg.get_scan_result.return_value = scan_result
    dlg.get_metadata.return_value = metadata or {
        "type": "Anime", "status": "Plan to Watch", "year": 0,
        "genres": "", "tags": "", "creator": "",
    }
    return dlg


class TestDirectoryImportTransaction:
    def test_cancelled_dialog_makes_no_changes(self, q_app):
        tab = _make_tab()
        dlg = MagicMock()
        dlg.exec.return_value = QDialog.DialogCode.Rejected
        with patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import._DirectoryImportDialog",
            return_value=dlg,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.get_library_db"
        ) as mock_get_db:
            tab._on_import_from_directory()
            mock_get_db.assert_not_called()

    def test_locked_vault_shows_warning_and_saves_nothing(self, q_app):
        tab = _make_tab()
        dlg = _mock_dialog(["Show A"], {"Show A": [(1, "/a/ep1.mp4")]})
        with patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import._DirectoryImportDialog",
            return_value=dlg,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.get_library_db",
            return_value=None,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.QMessageBox.warning"
        ) as mock_warn:
            tab._on_import_from_directory()
            mock_warn.assert_called_once()
        assert tab._entries == []

    def test_batch_commits_in_one_transaction(self, q_app):
        tab = _make_tab()
        scan_result = {
            "Show A": [(1, "/a/ep1.mp4"), (2, "/a/ep2.mp4")],
            "Show B": [(1, "/b/ep1.mp4")],
        }
        dlg = _mock_dialog(["Show A", "Show B"], scan_result)
        mock_raw_db = MagicMock()
        mock_raw_db.query.return_value = []  # no matching image groups
        mock_media_repo = MagicMock()

        with patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import._DirectoryImportDialog",
            return_value=dlg,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.get_library_db",
            return_value=mock_raw_db,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.MediaRepo",
            return_value=mock_media_repo,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.QMessageBox.information"
        ):
            tab._on_import_from_directory()

        mock_raw_db.begin.assert_called_once()
        mock_raw_db.commit.assert_called_once()
        mock_raw_db.rollback.assert_not_called()
        assert mock_media_repo.save_media.call_count == 2
        assert {e["title"] for e in tab._entries} == {"Show A", "Show B"}

    def test_matching_image_group_gets_linked(self, q_app):
        tab = _make_tab()
        scan_result = {"Show A": [(1, "/a/ep1.mp4")]}
        dlg = _mock_dialog(["Show A"], scan_result)
        mock_raw_db = MagicMock()
        # A groups row named exactly "Show A" (case-insensitive match).
        mock_raw_db.query.return_value = [(7, "Show A")]
        mock_media_repo = MagicMock()

        with patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import._DirectoryImportDialog",
            return_value=dlg,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.get_library_db",
            return_value=mock_raw_db,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.MediaRepo",
            return_value=mock_media_repo,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.QMessageBox.information"
        ):
            tab._on_import_from_directory()

        mock_media_repo.link_group.assert_called_once()
        args, _ = mock_media_repo.link_group.call_args
        assert args[1] == 7

    def test_save_failure_rolls_back_and_does_not_add_entries(self, q_app):
        tab = _make_tab()
        scan_result = {"Show A": [(1, "/a/ep1.mp4")]}
        dlg = _mock_dialog(["Show A"], scan_result)
        mock_raw_db = MagicMock()
        mock_raw_db.query.return_value = []
        mock_media_repo = MagicMock()
        mock_media_repo.save_media.side_effect = RuntimeError("disk full")

        with patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import._DirectoryImportDialog",
            return_value=dlg,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.get_library_db",
            return_value=mock_raw_db,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.MediaRepo",
            return_value=mock_media_repo,
        ), patch(
            "gui.src.tabs.database.series_listings_subtab._directory_import.QMessageBox.critical"
        ) as mock_crit:
            tab._on_import_from_directory()
            mock_crit.assert_called_once()

        mock_raw_db.rollback.assert_called_once()
        mock_raw_db.commit.assert_not_called()
        assert tab._entries == []
