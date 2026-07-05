import os
import shutil

from gui.src.windows.settings.app_settings import AppSettings
from PySide6.QtCore import QEvent, QObject, QSortFilterProxyModel, QUrl
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QAbstractItemView, QFileDialog, QInputDialog, QMenu, QMessageBox


class FileDialogEventFilter(QObject):
    def __init__(self, dialog: QFileDialog):
        super().__init__(dialog)
        self.dialog = dialog

    def _handle_favorite_action(self, path, favs, is_fav):
        if is_fav:
            if path in favs:
                favs.remove(path)
            AppSettings.set_favourite_directories(favs) # pyrefly: ignore [missing-attribute]
            self.dialog._sync_sidebar() # pyrefly: ignore [missing-attribute]
            QMessageBox.information(self.dialog, "Favourite Removed", f"Removed from favourites:\n{path}")
        else:
            favs.append(path)
            AppSettings.set_favourite_directories(favs) # pyrefly: ignore [missing-attribute]
            self.dialog._sync_sidebar() # pyrefly: ignore [missing-attribute]
            QMessageBox.information(self.dialog, "Favourite Added", f"Added to favourites:\n{path}")

    def _handle_new_folder_action(self, path):
        name, ok = QInputDialog.getText(self.dialog, "New Folder", "Enter folder name:")
        if ok and name.strip():
            new_dir_path = os.path.join(path, name.strip())
            try:
                os.makedirs(new_dir_path, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self.dialog, "Error", f"Failed to create folder: {e}")

    def _handle_rename_action(self, path):
        old_name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(self.dialog, "Rename Folder", f"Rename '{old_name}' to:", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            new_path = os.path.join(os.path.dirname(path), new_name.strip())
            try:
                os.rename(path, new_path)
            except Exception as e:
                QMessageBox.critical(self.dialog, "Error", f"Failed to rename folder: {e}")

    def _handle_delete_action(self, path):
        reply = QMessageBox.question(
            self.dialog,
            "Confirm Delete",
            f"Are you sure you want to delete this folder and all its contents?\n{path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(path)
            except Exception as e:
                QMessageBox.critical(self.dialog, "Error", f"Failed to delete folder: {e}")

    def eventFilter(self, watched, event):
        if event.type() != QEvent.Type.ContextMenu:
            return False

        index = watched.indexAt(event.pos())
        if not index.isValid():
            return False

        model = watched.model()

        actual_index = index
        actual_model = model
        while isinstance(actual_model, QSortFilterProxyModel):
            actual_index = actual_model.mapToSource(actual_index)
            actual_model = actual_model.sourceModel()

        path = actual_model.filePath(actual_index) if hasattr(actual_model, "filePath") else ""

        if not path or not os.path.isdir(path):
            return False

        menu = QMenu(watched)

        # Premium Modern Styling matching the application theme
        is_dark = AppSettings.get("preferences/theme", "dark") == "dark"
        if is_dark:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2d2d30;
                    color: white;
                    border: 1px solid #3e3e42;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 12px;
                }
                QMenu::item {
                    padding: 6px 20px;
                }
                QMenu::item:selected {
                    background-color: #00bcd4;
                    color: black;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #3e3e42;
                    margin: 4px 0px;
                }
            """)
        else:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #ffffff;
                    color: #333;
                    border: 1px solid #ccc;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 12px;
                }
                QMenu::item {
                    padding: 6px 20px;
                }
                QMenu::item:selected {
                    background-color: #007AFF;
                    color: white;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #ccc;
                    margin: 4px 0px;
                }
            """)

        favs = AppSettings.favourite_directories() # pyrefly: ignore [missing-attribute]
        is_fav = path in favs
        fav_action = QAction("❌ Remove from Favourites", menu) if is_fav else QAction("⭐ Add to Favourites", menu)

        menu.addAction(fav_action)
        menu.addSeparator()

        new_folder_act = QAction("New Folder", menu)
        rename_act = QAction("Rename", menu)
        delete_act = QAction("Delete", menu)

        menu.addAction(new_folder_act)
        menu.addAction(rename_act)
        menu.addAction(delete_act)

        action = menu.exec(event.globalPos())
        if action == fav_action:
            self._handle_favorite_action(path, favs, is_fav)
        elif action == new_folder_act:
            self._handle_new_folder_action(path)
        elif action == rename_act:
            self._handle_rename_action(path)
        elif action == delete_act:
            self._handle_delete_action(path)
        return True

class CustomFileDialog(QFileDialog):
    def __init__(self, parent=None, caption="", directory="", filter=""):
        super().__init__(parent, caption, directory, filter)
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self._default_sidebar_urls = self.sidebarUrls()
        self._sync_sidebar()
        self._filter = FileDialogEventFilter(self)
        self._install_filters()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_sidebar()
        self._install_filters()

    def setOptions(self, options):
        super().setOptions(options | QFileDialog.Option.DontUseNativeDialog)

    def setOption(self, option, on=True):
        if option == QFileDialog.Option.DontUseNativeDialog and not on:
            return
        super().setOption(option, on)

    def _sync_sidebar(self):
        favs = AppSettings.favourite_directories() # pyrefly: ignore [missing-attribute]
        system_urls = []
        for url in self._default_sidebar_urls:
            if url.isLocalFile():
                if url.toLocalFile() not in favs:
                    system_urls.append(url)
            else:
                system_urls.append(url)
        new_urls = system_urls + [QUrl.fromLocalFile(p) for p in favs]
        self.setSidebarUrls(new_urls)

    def _install_filters(self):
        for view in self.findChildren(QAbstractItemView):
            view.installEventFilter(self._filter)

def my_getExistingDirectory(parent=None, caption="", dir="", options=QFileDialog.Option.ShowDirsOnly):
    dialog = CustomFileDialog(parent, caption, dir)
    dialog.setFileMode(QFileDialog.FileMode.Directory)
    dialog.setOptions(options | QFileDialog.Option.DontUseNativeDialog)
    if dialog.exec() == QFileDialog.DialogCode.Accepted:
        selected = dialog.selectedFiles()
        if selected:
            return selected[0]
    return ""

# pyrefly: ignore [no-matching-overload]
def my_getOpenFileName(parent=None, caption="", dir="", filter="", selectedFilter="", options=None):
    if options is None:
        options = QFileDialog.Option()
    dialog = CustomFileDialog(parent, caption, dir, filter)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
    dialog.setOptions(options | QFileDialog.Option.DontUseNativeDialog)
    if selectedFilter:
        dialog.selectNameFilter(selectedFilter)
    if dialog.exec() == QFileDialog.DialogCode.Accepted:
        selected = dialog.selectedFiles()
        if selected:
            return selected[0], dialog.selectedNameFilter()
    return "", ""

# pyrefly: ignore [no-matching-overload]
def my_getOpenFileNames(parent=None, caption="", dir="", filter="", selectedFilter="", options=None):
    if options is None:
        options = QFileDialog.Option()
    dialog = CustomFileDialog(parent, caption, dir, filter)
    dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
    dialog.setOptions(options | QFileDialog.Option.DontUseNativeDialog)
    if selectedFilter:
        dialog.selectNameFilter(selectedFilter)
    if dialog.exec() == QFileDialog.DialogCode.Accepted:
        selected = dialog.selectedFiles()
        return selected, dialog.selectedNameFilter()
    return [], ""

# pyrefly: ignore [no-matching-overload]
def my_getSaveFileName(parent=None, caption="", dir="", filter="", selectedFilter="", options=None):
    if options is None:
        options = QFileDialog.Option()
    dialog = CustomFileDialog(parent, caption, dir, filter)
    dialog.setFileMode(QFileDialog.FileMode.AnyFile)
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setOptions(options | QFileDialog.Option.DontUseNativeDialog)
    if selectedFilter:
        dialog.selectNameFilter(selectedFilter)
    if dialog.exec() == QFileDialog.DialogCode.Accepted:
        selected = dialog.selectedFiles()
        if selected:
            return selected[0], dialog.selectedNameFilter()
    return "", ""

def apply_patch():
    QFileDialog.getExistingDirectory = staticmethod(my_getExistingDirectory)
    QFileDialog.getOpenFileName = staticmethod(my_getOpenFileName)
    QFileDialog.getOpenFileNames = staticmethod(my_getOpenFileNames)
    QFileDialog.getSaveFileName = staticmethod(my_getSaveFileName)
