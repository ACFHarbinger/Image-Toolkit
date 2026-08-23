"""DB.8b + Danbooru-style tag overhaul: detail-panel cross-domain link UI.

- _EntityDetailPanel "Linked Images" gallery strip.
- "+" add-tag action on both _DetailPanel (series) and _EntityDetailPanel.
"""

from unittest.mock import MagicMock, patch

import pytest

from gui.src.elements.database.display.detail_panel import _DetailPanel
from gui.src.elements.database.display.entity_detail_panel import _EntityDetailPanel

pytestmark = pytest.mark.gui


class TestDetailPanelAddTag:
    def test_no_entry_shows_hint_and_skips_dialog(self, q_app):
        panel = _DetailPanel()
        panel._entry_id = None

        with patch(
            "gui.src.elements.database.display.detail_panel._grouped_tags.QMessageBox.information"
        ) as mock_info:
            panel._on_add_tag()
            mock_info.assert_called_once()

    def test_add_tag_writes_and_refreshes(self, q_app):
        panel = _DetailPanel()
        panel._entry_id = "m-1"

        mock_db = MagicMock()
        mock_tag_repo = MagicMock()
        mock_tag_repo.list_categories.return_value = [{"name": "Genre", "color": "#e91e63"}]
        mock_tag_repo.get_all_tags.return_value = ["Action"]
        mock_media_repo = MagicMock()

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = True
        mock_dialog.get_data.return_value = ("Drama", "Genre")

        with (
            patch(
                "gui.src.elements.database.display.detail_panel._grouped_tags.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.elements.database.display.detail_panel._grouped_tags.TagRepo",
                return_value=mock_tag_repo,
            ),
            patch(
                "gui.src.elements.database.display.detail_panel._grouped_tags.MediaRepo",
                return_value=mock_media_repo,
            ),
            patch(
                "gui.src.elements.database.display.detail_panel._grouped_tags.AddTagDialog",
                return_value=mock_dialog,
            ),
        ):
            panel._on_add_tag()

        mock_media_repo.add_tag.assert_called_once_with("m-1", "Drama", "Genre")

    def test_add_tag_cancelled_dialog_writes_nothing(self, q_app):
        panel = _DetailPanel()
        panel._entry_id = "m-1"

        mock_db = MagicMock()
        mock_tag_repo = MagicMock()
        mock_tag_repo.list_categories.return_value = []
        mock_tag_repo.get_all_tags.return_value = []
        mock_media_repo = MagicMock()

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = False

        with (
            patch(
                "gui.src.elements.database.display.detail_panel._grouped_tags.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.elements.database.display.detail_panel._grouped_tags.TagRepo",
                return_value=mock_tag_repo,
            ),
            patch(
                "gui.src.elements.database.display.detail_panel._grouped_tags.MediaRepo",
                return_value=mock_media_repo,
            ),
            patch(
                "gui.src.elements.database.display.detail_panel._grouped_tags.AddTagDialog",
                return_value=mock_dialog,
            ),
        ):
            panel._on_add_tag()

        mock_media_repo.add_tag.assert_not_called()


class TestEntityDetailPanelAddTag:
    def test_no_entity_shows_hint_and_skips_dialog(self, q_app):
        panel = _EntityDetailPanel()
        panel._entity_id = None

        with patch(
            "gui.src.elements.database.display.entity_detail_panel.QMessageBox.information"
        ) as mock_info:
            panel._on_add_tag()
            mock_info.assert_called_once()

    def test_add_tag_writes_and_refreshes(self, q_app):
        panel = _EntityDetailPanel()
        panel._entity_id = "ent-1"

        mock_db = MagicMock()
        mock_tag_repo = MagicMock()
        mock_tag_repo.list_categories.return_value = [{"name": "Appearance", "color": "#1abc9c"}]
        mock_tag_repo.get_all_tags.return_value = ["blue_hair"]
        mock_entity_repo = MagicMock()

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = True
        mock_dialog.get_data.return_value = ("blue_hair", "Appearance")

        with (
            patch(
                "gui.src.elements.database.display.entity_detail_panel.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.elements.database.display.entity_detail_panel.TagRepo",
                return_value=mock_tag_repo,
            ),
            patch(
                "gui.src.elements.database.display.entity_detail_panel.EntityRepo",
                return_value=mock_entity_repo,
            ),
            patch(
                "gui.src.elements.database.display.entity_detail_panel.AddTagDialog",
                return_value=mock_dialog,
            ),
        ):
            panel._on_add_tag()

        mock_entity_repo.add_tag.assert_called_once_with("ent-1", "blue_hair", "Appearance")


class TestEntityDetailPanelLinkedImages:
    def test_no_entity_link_image_shows_hint(self, q_app):
        panel = _EntityDetailPanel()
        panel._entity_id = None

        with patch(
            "gui.src.elements.database.display.entity_detail_panel.QMessageBox.information"
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
                "gui.src.elements.database.display.entity_detail_panel.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.elements.database.display.entity_detail_panel.EntityRepo"
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
                "gui.src.elements.database.display.entity_detail_panel.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.elements.database.display.entity_detail_panel.ImageRepo",
                return_value=mock_image_repo,
            ),
            patch(
                "gui.src.elements.database.display.entity_detail_panel.EntityRepo",
                return_value=mock_entity_repo,
            ),
            patch(
                "gui.src.elements.database.display.entity_detail_panel.QFileDialog.getOpenFileName",
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
                "gui.src.elements.database.display.entity_detail_panel.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.elements.database.display.entity_detail_panel.ImageRepo",
                return_value=mock_image_repo,
            ),
            patch(
                "gui.src.elements.database.display.entity_detail_panel.EntityRepo",
                return_value=mock_entity_repo,
            ),
            patch(
                "gui.src.elements.database.display.entity_detail_panel.QFileDialog.getOpenFileName",
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
                "gui.src.elements.database.display.entity_detail_panel.get_library_db",
                return_value=mock_db,
            ),
            patch(
                "gui.src.elements.database.display.entity_detail_panel.EntityRepo",
                return_value=mock_entity_repo,
            ),
        ):
            panel._unlink_image(42)

        mock_entity_repo.unlink_image.assert_called_once_with("ent-1", 42)
