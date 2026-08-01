"""DB.8a/DB.8b: detail-panel cross-domain link UI.

- _DetailPanel (content listings) "Linked Image Groups" chip row + dialog.
- _EntityDetailPanel "Linked Images" gallery strip.
"""

from unittest.mock import MagicMock, patch

import pytest
from gui.src.tabs.core.elements.display.detail_panel import _DetailPanel
from gui.src.tabs.core.elements.display.entity_detail_panel import _EntityDetailPanel

pytestmark = pytest.mark.gui


class TestDetailPanelLinkedGroups:
    def test_no_entry_shows_hint_and_skips_dialog(self, q_app):
        panel = _DetailPanel()
        panel._entry_id = None

        with patch(
            "gui.src.tabs.core.elements.display.detail_panel._linked_groups.QMessageBox.information"
        ) as mock_info:
            panel._select_linked_groups()
            mock_info.assert_called_once()

    def test_refresh_display_empty_when_no_entry(self, q_app):
        panel = _DetailPanel()
        panel._entry_id = None
        panel._refresh_linked_groups_display()
        assert panel.f_linked_groups_display.toPlainText() == ""

    def test_refresh_display_shows_linked_group_names(self, q_app):
        panel = _DetailPanel()
        panel._entry_id = "m-1"

        mock_db = MagicMock()
        with (
            patch(
                "gui.src.tabs.core.elements.display.detail_panel._linked_groups.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.tabs.core.elements.display.detail_panel._linked_groups.MediaRepo"
            ) as MockMediaRepo,
        ):
            MockMediaRepo.return_value.get_linked_groups.return_value = [
                {"id": 1, "name": "Beach Trip"},
                {"id": 2, "name": "Cowboy Bebop Scans"},
            ]
            panel._refresh_linked_groups_display()

        assert panel.f_linked_groups_display.toPlainText() == "Beach Trip, Cowboy Bebop Scans"

    def test_select_linked_groups_links_and_unlinks_diff(self, q_app):
        panel = _DetailPanel()
        panel._entry_id = "m-1"
        panel.f_title.setText("Cowboy Bebop")

        mock_db = MagicMock()
        mock_image_repo = MagicMock()
        mock_image_repo.get_all_groups.return_value = ["Kept", "ToRemove", "ToAdd"]
        mock_image_repo.add_group.side_effect = lambda name: {"ToAdd": 3, "ToRemove": 2}[name]

        mock_media_repo = MagicMock()
        mock_media_repo.get_linked_groups.return_value = [
            {"id": 1, "name": "Kept"},
            {"id": 2, "name": "ToRemove"},
        ]
        mock_media_repo.suggest_group_matches.return_value = ["Kept"]

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = True
        mock_dialog.get_selected_names.return_value = ["Kept", "ToAdd"]

        with (
            patch(
                "gui.src.tabs.core.elements.display.detail_panel._linked_groups.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.tabs.core.elements.display.detail_panel._linked_groups.ImageRepo",
                return_value=mock_image_repo,
            ),
            patch(
                "gui.src.tabs.core.elements.display.detail_panel._linked_groups.MediaRepo",
                return_value=mock_media_repo,
            ),
            patch(
                "gui.src.tabs.core.elements.display.detail_panel._linked_groups._LinkedGroupsDialog",
                return_value=mock_dialog,
            ),
        ):
            panel._select_linked_groups()

        mock_media_repo.link_group.assert_called_once_with("m-1", 3)
        mock_media_repo.unlink_group.assert_called_once_with("m-1", 2)

    def test_select_linked_groups_cancelled_dialog_makes_no_changes(self, q_app):
        panel = _DetailPanel()
        panel._entry_id = "m-1"

        mock_db = MagicMock()
        mock_media_repo = MagicMock()
        mock_media_repo.get_linked_groups.return_value = []
        mock_media_repo.suggest_group_matches.return_value = []

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = False

        with (
            patch(
                "gui.src.tabs.core.elements.display.detail_panel._linked_groups.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.tabs.core.elements.display.detail_panel._linked_groups.ImageRepo"
            ) as MockImageRepo,
            patch(
                "gui.src.tabs.core.elements.display.detail_panel._linked_groups.MediaRepo",
                return_value=mock_media_repo,
            ),
            patch(
                "gui.src.tabs.core.elements.display.detail_panel._linked_groups._LinkedGroupsDialog",
                return_value=mock_dialog,
            ),
        ):
            MockImageRepo.return_value.get_all_groups.return_value = ["G"]
            panel._select_linked_groups()

        mock_media_repo.link_group.assert_not_called()
        mock_media_repo.unlink_group.assert_not_called()


class TestEntityDetailPanelLinkedImages:
    def test_no_entity_link_image_shows_hint(self, q_app):
        panel = _EntityDetailPanel()
        panel._entity_id = None

        with patch(
            "gui.src.tabs.core.elements.display.entity_detail_panel.QMessageBox.information"
        ) as mock_info:
            panel._link_image()
            mock_info.assert_called_once()

    def test_refresh_linked_images_empty_when_no_entity(self, q_app):
        panel = _EntityDetailPanel()
        panel._entity_id = None
        panel._refresh_linked_images()
        # Only the trailing stretch remains -- no thumbnail widgets added.
        assert panel.linked_images_layout.count() == 1

    def test_refresh_linked_images_renders_one_cell_per_image(self, q_app):
        panel = _EntityDetailPanel()
        panel._entity_id = "ent-1"

        mock_db = MagicMock()
        with (
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.EntityRepo"
            ) as MockEntityRepo,
        ):
            MockEntityRepo.return_value.get_linked_images.return_value = [
                {"id": 10, "file_path": "/a.png"},
                {"id": 11, "file_path": "/b.png"},
            ]
            panel._refresh_linked_images()

        # 2 image cells + 1 trailing stretch.
        assert panel.linked_images_layout.count() == 3

    def test_link_image_resolves_existing_indexed_image(self, q_app):
        panel = _EntityDetailPanel()
        panel._entity_id = "ent-1"

        mock_db = MagicMock()
        mock_image_repo = MagicMock()
        mock_image_repo.get_image_by_path.return_value = {"id": 42}
        mock_entity_repo = MagicMock()

        with (
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.ImageRepo",
                return_value=mock_image_repo,
            ),
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.EntityRepo",
                return_value=mock_entity_repo,
            ),
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.QFileDialog.getOpenFileName",
                return_value=("/already/indexed.png", ""),
            ),
        ):
            panel._link_image()

        mock_image_repo.add_image.assert_not_called()
        mock_entity_repo.link_image.assert_called_once_with("ent-1", 42)

    def test_link_image_indexes_new_image_first(self, q_app):
        panel = _EntityDetailPanel()
        panel._entity_id = "ent-1"

        mock_db = MagicMock()
        mock_image_repo = MagicMock()
        mock_image_repo.get_image_by_path.return_value = None
        mock_image_repo.add_image.return_value = 99
        mock_entity_repo = MagicMock()

        with (
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.ImageRepo",
                return_value=mock_image_repo,
            ),
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.EntityRepo",
                return_value=mock_entity_repo,
            ),
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.QFileDialog.getOpenFileName",
                return_value=("/new/photo.png", ""),
            ),
        ):
            panel._link_image()

        mock_image_repo.add_image.assert_called_once_with("/new/photo.png", tags=[])
        mock_entity_repo.link_image.assert_called_once_with("ent-1", 99)

    def test_unlink_image(self, q_app):
        panel = _EntityDetailPanel()
        panel._entity_id = "ent-1"

        mock_db = MagicMock()
        mock_entity_repo = MagicMock()
        with (
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.tabs.core.elements.display.entity_detail_panel.EntityRepo",
                return_value=mock_entity_repo,
            ),
        ):
            panel._unlink_image(42)

        mock_entity_repo.unlink_image.assert_called_once_with("ent-1", 42)
