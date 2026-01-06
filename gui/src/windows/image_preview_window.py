import os
from typing import List
from PySide6.QtCore import Qt, QObject, Slot, Property, Signal, QUrl
from PySide6.QtQml import QQmlApplicationEngine


class ImagePreviewWindow(QObject):
    """
    A logic provider for the Image Preview QML window.
    """
    path_changed = Signal(str, str) # old_path, new_path
    data_changed = Signal()

    def __init__(
        self,
        image_path: str,
        db_tab_ref=None,
        parent=None,
        all_paths: List[str] = None,
        start_index: int = 0,
    ):
        super().__init__(parent)
        self.all_paths = all_paths if all_paths is not None else [image_path]
        self.current_index = start_index
        self.db_tab_ref = db_tab_ref
        
        # QML Setup
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("backend", self)
        
        qml_path = os.path.join(os.path.dirname(__file__), "..", "..", "qml", "windows", "ImagePreviewWindow.qml")
        self.engine.load(QUrl.fromLocalFile(os.path.abspath(qml_path)))
        
        if not self.engine.rootObjects():
            print("Error: Could not load ImagePreviewWindow.qml")
            return
            
        self.root = self.engine.rootObjects()[0]
        
    @Property(str, notify=data_changed)
    def currentImagePath(self):
        if 0 <= self.current_index < len(self.all_paths):
            path = self.all_paths[self.current_index]
            # Convert to file URL for QML if needed, but QML Image can often take local paths
            return QUrl.fromLocalFile(os.path.abspath(path)).toString()
        return ""

    @Property(str, notify=data_changed)
    def navigationInfo(self):
        return f"{self.current_index + 1} / {len(self.all_paths)}"

    @Slot()
    def next(self):
        if not self.all_paths: return
        old_path = self.all_paths[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.all_paths)
        new_path = self.all_paths[self.current_index]
        self.path_changed.emit(old_path, new_path)
        self.data_changed.emit()

    @Slot()
    def previous(self):
        if not self.all_paths: return
        old_path = self.all_paths[self.current_index]
        self.current_index = (self.current_index - 1) % len(self.all_paths)
        new_path = self.all_paths[self.current_index]
        self.path_changed.emit(old_path, new_path)
        self.data_changed.emit()

    def show(self):
        if hasattr(self, 'root'):
            self.root.show()

    def activateWindow(self):
        if hasattr(self, 'root'):
            self.root.raise_()
            self.root.requestActivate()

    def close(self):
        if hasattr(self, 'root'):
            self.root.close()

    @property
    def image_path(self):
        # Backward compatibility for code checking if win.image_path == ...
        if 0 <= self.current_index < len(self.all_paths):
            return self.all_paths[self.current_index]
        return ""
