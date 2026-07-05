from unittest.mock import patch

from gui.src.utils.file_dialog_patch import CustomFileDialog, FileDialogEventFilter
from gui.src.windows.settings.app_settings import AppSettings
from PySide6.QtCore import QPoint
from PySide6.QtGui import QContextMenuEvent, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QFileDialog, QListView, QMenu, QMessageBox


class MyStandardItemModel(QStandardItemModel):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._path = path
    def filePath(self, index):
        return self._path


class MyMenu(QMenu):
    def exec(self, *args, **kwargs):
        # Return the first action added (which is the favourites action)
        return self.actions()[0]


class TestFileDialogPatch:
    def test_custom_file_dialog_initialization(self, q_app):
        # Clean current favourites
        AppSettings.set_favourite_directories([])

        dialog = CustomFileDialog()
        # Verify DontUseNativeDialog is set
        assert dialog.testOption(QFileDialog.Option.DontUseNativeDialog) is True

        # Verify options forcing
        dialog.setOptions(QFileDialog.Option.ShowDirsOnly)
        assert dialog.testOption(QFileDialog.Option.DontUseNativeDialog) is True

        # Verify single option forcing
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, False)
        assert dialog.testOption(QFileDialog.Option.DontUseNativeDialog) is True

    def test_sync_sidebar(self, q_app, tmp_path):
        fav1 = str(tmp_path / "fav1")
        fav2 = str(tmp_path / "fav2")
        AppSettings.set_favourite_directories([fav1, fav2])

        dialog = CustomFileDialog()
        sidebar_urls = [u.toLocalFile() for u in dialog.sidebarUrls() if u.isLocalFile()]
        assert fav1 in sidebar_urls
        assert fav2 in sidebar_urls

        # Now remove one and sync
        AppSettings.set_favourite_directories([fav1])
        dialog._sync_sidebar()
        sidebar_urls = [u.toLocalFile() for u in dialog.sidebarUrls() if u.isLocalFile()]
        assert fav1 in sidebar_urls
        assert fav2 not in sidebar_urls

        AppSettings.set_favourite_directories([])

    def test_event_filter_context_menu_add_favourite(self, q_app, tmp_path):
        AppSettings.set_favourite_directories([])

        dialog = CustomFileDialog()
        event_filter = FileDialogEventFilter(dialog)

        # Setup target directory
        target_dir = tmp_path / "new_fav"
        target_dir.mkdir()

        # Create a real QListView and model
        mock_view = QListView(dialog)
        model = MyStandardItemModel(str(target_dir), mock_view)
        mock_view.setModel(model)

        # Add an item to get a valid index
        item = QStandardItem("test_item")
        model.appendRow(item)
        valid_index = model.indexFromItem(item)

        # Mock indexAt
        mock_view.indexAt = lambda pos: valid_index

        # Create a real QContextMenuEvent
        event = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            QPoint(10, 10),
            QPoint(100, 100)
        )

        # Patch QMenu class to be MyMenu
        with patch("gui.src.utils.file_dialog_patch.QMenu", MyMenu), \
             patch.object(QMessageBox, "information") as mock_info:

            res = event_filter.eventFilter(mock_view, event)
            assert res is True

            # Verify the directory was added to favourites
            assert str(target_dir) in AppSettings.favourite_directories()
            mock_info.assert_called_once()

        AppSettings.set_favourite_directories([])
