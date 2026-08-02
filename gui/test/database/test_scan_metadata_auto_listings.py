"""Tests for DB.8d (scoped): auto-create/link listings from newly-scanned
image groups (gui/src/tabs/database/scan_metadata_tab/_auto_listings.py).
"""

from unittest.mock import MagicMock, patch

import pytest
from gui.src.elements.scan_metadata_tab import ScanMetadataTab
from PySide6.QtWidgets import QDialog

pytestmark = pytest.mark.gui


def _make_tab():
    mock_db_tab = MagicMock()
    with patch(
        "gui.src.elements.scan_metadata_tab._ui_builder.LOCAL_SOURCE_PATH", "/tmp"
    ):
        return ScanMetadataTab(mock_db_tab)


class TestMaybeOfferAutoListings:
    def test_empty_touched_groups_is_noop(self, q_app):
        tab = _make_tab()
        with patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.get_library_db"
        ) as mock_get_db:
            tab._maybe_offer_auto_listings([])
            mock_get_db.assert_not_called()

    def test_no_session_is_noop(self, q_app):
        tab = _make_tab()
        with patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.get_library_db",
            return_value=None,
        ):
            # Should not raise even though the session is unavailable.
            tab._maybe_offer_auto_listings(["Some Group"])

    def test_group_already_linked_is_skipped(self, q_app):
        tab = _make_tab()
        mock_image_repo = MagicMock()
        mock_image_repo.add_group.return_value = 5
        mock_media_repo = MagicMock()
        mock_media_repo.list_ids_and_titles.return_value = []
        mock_media_repo.get_media_for_group.return_value = [{"id": "m-1", "title": "X"}]

        with patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.get_library_db",
            return_value=MagicMock(),
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.ImageRepo",
            return_value=mock_image_repo,
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.MediaRepo",
            return_value=mock_media_repo,
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings._AutoListingsReviewDialog"
        ) as mock_dialog_cls:
            tab._maybe_offer_auto_listings(["Linked Group"])
            mock_dialog_cls.assert_not_called()

    def test_new_group_shows_dialog_and_creates_on_accept(self, q_app):
        tab = _make_tab()
        mock_raw_db = MagicMock()
        mock_image_repo = MagicMock()
        mock_image_repo.add_group.return_value = 9
        mock_media_repo = MagicMock()
        mock_media_repo.list_ids_and_titles.return_value = []
        mock_media_repo.get_media_for_group.return_value = []
        mock_media_repo.suggest_group_matches.return_value = []
        mock_media_repo.save_media.return_value = "m-new"

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_dialog.decisions.return_value = [
            {"action": "new", "group_id": 9, "title": "New Series"}
        ]

        with patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.get_library_db",
            return_value=mock_raw_db,
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.ImageRepo",
            return_value=mock_image_repo,
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.MediaRepo",
            return_value=mock_media_repo,
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings._AutoListingsReviewDialog",
            return_value=mock_dialog,
        ):
            tab._maybe_offer_auto_listings(["New Series"])

        mock_raw_db.begin.assert_called_once()
        mock_media_repo.save_media.assert_called_once_with({"title": "New Series"})
        mock_media_repo.link_group.assert_called_once_with("m-new", 9)
        mock_raw_db.commit.assert_called_once()
        mock_raw_db.rollback.assert_not_called()

    def test_cancelled_dialog_makes_no_changes(self, q_app):
        tab = _make_tab()
        mock_raw_db = MagicMock()
        mock_image_repo = MagicMock()
        mock_image_repo.add_group.return_value = 9
        mock_media_repo = MagicMock()
        mock_media_repo.list_ids_and_titles.return_value = []
        mock_media_repo.get_media_for_group.return_value = []
        mock_media_repo.suggest_group_matches.return_value = []

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Rejected

        with patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.get_library_db",
            return_value=mock_raw_db,
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.ImageRepo",
            return_value=mock_image_repo,
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.MediaRepo",
            return_value=mock_media_repo,
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings._AutoListingsReviewDialog",
            return_value=mock_dialog,
        ):
            tab._maybe_offer_auto_listings(["Some Group"])

        mock_media_repo.save_media.assert_not_called()
        mock_media_repo.link_group.assert_not_called()
        mock_raw_db.begin.assert_not_called()

    def test_whole_word_match_suggests_existing(self, q_app):
        """A group name sharing a whole word with an existing title should
        be offered as a "link to existing" candidate, not just any
        substring hit (the noise-reduction gate)."""
        tab = _make_tab()
        mock_image_repo = MagicMock()
        mock_image_repo.add_group.return_value = 3
        mock_media_repo = MagicMock()
        mock_media_repo.list_ids_and_titles.return_value = [("m-1", "Cowboy Bebop")]
        mock_media_repo.get_media_for_group.return_value = []
        mock_media_repo.suggest_group_matches.return_value = ["Cowboy Bebop"]

        captured = {}

        def _capture_dialog(candidates, parent):
            captured["candidates"] = candidates
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
            return mock_dialog

        with patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.get_library_db",
            return_value=MagicMock(),
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.ImageRepo",
            return_value=mock_image_repo,
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings.MediaRepo",
            return_value=mock_media_repo,
        ), patch(
            "gui.src.elements.scan_metadata_tab._auto_listings._AutoListingsReviewDialog",
            side_effect=_capture_dialog,
        ):
            tab._maybe_offer_auto_listings(["Cowboy Bebop Scans (RAW)"])

        assert captured["candidates"][0]["suggested_title"] == "Cowboy Bebop"
        assert captured["candidates"][0]["suggested_media_id"] == "m-1"
