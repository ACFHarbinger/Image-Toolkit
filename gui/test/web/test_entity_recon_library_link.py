"""Tests for EntityReconTab's "Link to Library Entity" action (DB.8b).

gui/src/tabs/web/entity_recon_tab/_library_link.py
"""

from unittest.mock import MagicMock, patch

import pytest
from gui.src.tabs.web.entity_recon_tab import EntityReconTab
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem

pytestmark = pytest.mark.gui


def _make_local_match_item(path: str) -> QTreeWidgetItem:
    item = QTreeWidgetItem(["Some Person", "88%"])
    item.setData(0, Qt.ItemDataRole.UserRole, ("local", path))
    return item


class TestLibraryLinkGating:
    def test_link_requires_open_session(self, q_app):
        tab = EntityReconTab()
        tab.name_label.setText("Some Person")

        with (
            patch(
                "backend.src.database.unified.session.is_open", return_value=False
            ),
            patch(
                "gui.src.tabs.web.entity_recon_tab._library_link.QMessageBox.information"
            ) as mock_info,
        ):
            tab._link_match_to_library("/tmp/does-not-matter.png")
            mock_info.assert_called_once()
            assert "isn't open" in mock_info.call_args[0][2].lower()

    def test_link_requires_known_name(self, q_app):
        tab = EntityReconTab()
        tab.name_label.setText("Unknown")

        with (
            patch(
                "backend.src.database.unified.session.is_open", return_value=True
            ),
            patch(
                "gui.src.tabs.web.entity_recon_tab._library_link.QMessageBox.information"
            ) as mock_info,
        ):
            tab._link_match_to_library("/tmp/does-not-matter.png")
            mock_info.assert_called_once()
            assert "identity" in mock_info.call_args[0][2].lower()

    def test_link_requires_existing_file(self, q_app, tmp_path):
        tab = EntityReconTab()
        tab.name_label.setText("Some Person")
        missing = str(tmp_path / "gone.png")

        with (
            patch(
                "backend.src.database.unified.session.is_open", return_value=True
            ),
            patch(
                "gui.src.tabs.web.entity_recon_tab._library_link.QMessageBox.warning"
            ) as mock_warn,
        ):
            tab._link_match_to_library(missing)
            mock_warn.assert_called_once()


class TestLibraryLinkFlow:
    def test_links_to_existing_image_and_entity(self, q_app, tmp_path):
        tab = EntityReconTab()
        tab.name_label.setText("Ada Lovelace")
        p = tmp_path / "match.png"
        p.write_bytes(b"x")

        mock_db = MagicMock()
        mock_image_repo = MagicMock()
        mock_image_repo.get_image_by_path.return_value = {"id": 7}
        mock_entity_repo = MagicMock()
        mock_entity_repo.name_map.return_value = {"ent-1": "Ada Lovelace"}

        with (
            patch(
                "backend.src.database.unified.session.is_open", return_value=True
            ),
            patch(
                "backend.src.database.unified.session.get_session",
                return_value=mock_db,
            ),
            patch(
                "backend.src.database.unified.image_repo.ImageRepo",
                return_value=mock_image_repo,
            ),
            patch(
                "backend.src.database.unified.entity_repo.EntityRepo",
                return_value=mock_entity_repo,
            ),
            patch(
                "gui.src.tabs.web.entity_recon_tab._library_link.QMessageBox.question",
                return_value=__import__(
                    "PySide6.QtWidgets", fromlist=["QMessageBox"]
                ).QMessageBox.StandardButton.Yes,
            ),
            patch(
                "gui.src.tabs.web.entity_recon_tab._library_link.QMessageBox.information"
            ),
        ):
            tab._link_match_to_library(str(p))

        mock_image_repo.add_image.assert_not_called()
        mock_entity_repo.link_image.assert_called_once_with("ent-1", 7)

    def test_creates_new_image_and_new_entity_on_confirm(self, q_app, tmp_path):
        tab = EntityReconTab()
        tab.name_label.setText("Brand New Person")
        p = tmp_path / "match.png"
        p.write_bytes(b"x")

        mock_db = MagicMock()
        mock_image_repo = MagicMock()
        mock_image_repo.get_image_by_path.return_value = None
        mock_image_repo.add_image.return_value = 42
        mock_entity_repo = MagicMock()
        mock_entity_repo.name_map.return_value = {}
        mock_entity_repo.save_entity.return_value = "ent-new"

        from PySide6.QtWidgets import QMessageBox

        with (
            patch(
                "backend.src.database.unified.session.is_open", return_value=True
            ),
            patch(
                "backend.src.database.unified.session.get_session",
                return_value=mock_db,
            ),
            patch(
                "backend.src.database.unified.image_repo.ImageRepo",
                return_value=mock_image_repo,
            ),
            patch(
                "backend.src.database.unified.entity_repo.EntityRepo",
                return_value=mock_entity_repo,
            ),
            patch(
                "gui.src.tabs.web.entity_recon_tab._library_link.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch(
                "gui.src.tabs.web.entity_recon_tab._library_link.QMessageBox.information"
            ),
        ):
            tab._link_match_to_library(str(p))

        mock_image_repo.add_image.assert_called_once_with(str(p), tags=[])
        mock_entity_repo.save_entity.assert_called_once_with(
            {"name": "Brand New Person"}
        )
        mock_entity_repo.link_image.assert_called_once_with("ent-new", 42)

    def test_declining_confirmation_does_not_link(self, q_app, tmp_path):
        tab = EntityReconTab()
        tab.name_label.setText("Ada Lovelace")
        p = tmp_path / "match.png"
        p.write_bytes(b"x")

        mock_db = MagicMock()
        mock_image_repo = MagicMock()
        mock_image_repo.get_image_by_path.return_value = {"id": 7}
        mock_entity_repo = MagicMock()
        mock_entity_repo.name_map.return_value = {"ent-1": "Ada Lovelace"}

        from PySide6.QtWidgets import QMessageBox

        with (
            patch(
                "backend.src.database.unified.session.is_open", return_value=True
            ),
            patch(
                "backend.src.database.unified.session.get_session",
                return_value=mock_db,
            ),
            patch(
                "backend.src.database.unified.image_repo.ImageRepo",
                return_value=mock_image_repo,
            ),
            patch(
                "backend.src.database.unified.entity_repo.EntityRepo",
                return_value=mock_entity_repo,
            ),
            patch(
                "gui.src.tabs.web.entity_recon_tab._library_link.QMessageBox.question",
                return_value=QMessageBox.StandardButton.No,
            ),
        ):
            tab._link_match_to_library(str(p))

        mock_entity_repo.link_image.assert_not_called()


class TestProvContextMenu:
    def test_context_menu_ignores_web_matches(self, q_app):
        tab = EntityReconTab()
        item = QTreeWidgetItem(["example.com", ""])
        item.setData(0, Qt.ItemDataRole.UserRole, ("web", "https://example.com"))
        tab.prov_tree.addTopLevelItem(item)

        with patch.object(
            tab, "_link_match_to_library"
        ) as mock_link, patch.object(
            tab.prov_tree, "itemAt", return_value=item
        ), patch(
            "gui.src.tabs.web.entity_recon_tab._library_link.QMenu"
        ) as MockMenu:
            mock_menu_instance = MockMenu.return_value
            mock_menu_instance.exec.return_value = None
            tab._on_prov_context_menu(tab.prov_tree.visualItemRect(item).topLeft())
            mock_link.assert_not_called()
