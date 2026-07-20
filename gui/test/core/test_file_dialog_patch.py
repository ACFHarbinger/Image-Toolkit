from unittest.mock import patch

from gui.src.windows.settings.file_dialog_patch import CustomFileDialog, FileDialogEventFilter
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
        with patch("gui.src.windows.settings.file_dialog_patch.QMenu", MyMenu), \
             patch.object(QMessageBox, "information") as mock_info:

            res = event_filter.eventFilter(mock_view, event)
            assert res is True

            # Verify the directory was added to favourites
            assert str(target_dir) in AppSettings.favourite_directories()
            mock_info.assert_called_once()

        AppSettings.set_favourite_directories([])

    def test_event_filter_context_menu_remove_favourite(self, q_app, tmp_path):
        target_dir = tmp_path / "fav_to_remove"
        target_dir.mkdir()
        AppSettings.set_favourite_directories([str(target_dir)])

        dialog = CustomFileDialog()
        event_filter = FileDialogEventFilter(dialog)

        mock_view = QListView(dialog)
        model = MyStandardItemModel(str(target_dir), mock_view)
        mock_view.setModel(model)

        item = QStandardItem("test_item")
        model.appendRow(item)
        valid_index = model.indexFromItem(item)

        mock_view.indexAt = lambda pos: valid_index

        event = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            QPoint(10, 10),
            QPoint(100, 100)
        )

        with patch("gui.src.windows.settings.file_dialog_patch.QMenu", MyMenu), \
             patch.object(QMessageBox, "information") as mock_info:

            res = event_filter.eventFilter(mock_view, event)
            assert res is True

            # Verify the directory was removed from favourites
            assert str(target_dir) not in AppSettings.favourite_directories()
            mock_info.assert_called_once()

        AppSettings.set_favourite_directories([])

    def test_thumbnail_file_picker_favourites(self, q_app, tmp_path):
        from gui.src.tabs.animation.stitch_tab import _ThumbnailFilePicker
        from PySide6.QtCore import Qt

        fav_dir = tmp_path / "picker_fav"
        fav_dir.mkdir()
        AppSettings.set_favourite_directories([str(fav_dir)])

        picker = _ThumbnailFilePicker(start_dir=str(tmp_path))

        # Verify favourite directory is in sidebar
        sidebar_paths = [
            picker._sidebar.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(picker._sidebar.count())
        ]
        assert str(fav_dir) in sidebar_paths

        # Test context menu remove on sidebar
        with patch.object(QMessageBox, "information"):
            # Find item corresponding to fav_dir
            target_item = None
            for i in range(picker._sidebar.count()):
                item = picker._sidebar.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == str(fav_dir):
                    target_item = item
                    break
            assert target_item is not None

            # Simulate context menu action trigger
            pos = picker._sidebar.visualItemRect(target_item).center()
            with patch("gui.src.tabs.animation.stitch_tab.QMenu", MyMenu):
                picker._on_sidebar_context_menu(pos)

            assert str(fav_dir) not in AppSettings.favourite_directories()

        AppSettings.set_favourite_directories([])
