"""Thumbnail-grid file picker dialog for visual image selection.

Displays async thumbnail previews with sidebar bookmarks, adjustable thumbnail sizes,
and folder navigation.
"""

from __future__ import annotations

import os
from typing import Optional, Sequence

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

try:
    from ...windows.settings.app_settings import AppSettings
    from ...windows.settings.splitter_persistence import persist_splitter
except ImportError:
    AppSettings = None  # type: ignore[assignment]
    persist_splitter = None  # type: ignore[assignment]


class _ThumbHub(QObject):
    loaded = Signal(str, int, object)  # path, generation, QImage


class _ThumbTask(QRunnable):
    def __init__(self, path: str, size: int, generation: int, hub: _ThumbHub):
        super().__init__()
        self._path = path
        self._size = size
        self._gen = generation
        self._hub = hub
        self.setAutoDelete(True)

    def run(self) -> None:
        img = QImage(self._path)
        if not img.isNull():
            img = img.scaled(
                self._size,
                self._size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._hub.loaded.emit(self._path, self._gen, img)


class ThumbnailFilePicker(QDialog):
    """File picker dialog with visual thumbnail previews."""

    _DEFAULT_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"}

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        caption: str = "Select Image",
        start_dir: str = "",
        filter_exts: Optional[Sequence[str]] = None,
        single_selection: bool = False,
    ):
        super().__init__(parent)
        self.setWindowTitle(caption)
        self.resize(960, 640)

        # Resolve starting directory
        if start_dir and os.path.isfile(start_dir):
            start_dir = os.path.dirname(start_dir)
        if not start_dir or not os.path.isdir(start_dir):
            pictures = os.path.expanduser("~/Pictures")
            start_dir = pictures if os.path.isdir(pictures) else os.path.expanduser("~")

        self._current_dir = start_dir
        self._single_selection = single_selection
        self._exts = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in filter_exts} if filter_exts else self._DEFAULT_EXTS
        self._selected_paths: list[str] = []
        self._item_map: dict[str, QListWidgetItem] = {}
        self._generation = 0
        self._pool = QThreadPool.globalInstance()
        self._hub = _ThumbHub()
        self._hub.loaded.connect(self._on_thumb_loaded)
        self._thumb_size = 128
        self._folder_icon = ThumbnailFilePicker._make_folder_icon(64)
        self._build_ui()
        self._navigate(self._current_dir)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Navigation bar
        nav = QHBoxLayout()
        btn_up = QPushButton("↑ Up")
        btn_up.setFixedWidth(80)
        btn_up.clicked.connect(self._go_up)
        self._addr_bar = QLineEdit()
        self._addr_bar.returnPressed.connect(
            lambda: self._navigate(self._addr_bar.text())
        )
        nav.addWidget(btn_up)
        nav.addWidget(self._addr_bar)
        layout.addLayout(nav)

        # Sidebar + thumbnail grid
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._sidebar = QListWidget()
        self._sidebar.setMaximumWidth(160)
        self._sidebar.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._sidebar.setFrameShape(QListWidget.Shape.NoFrame)
        self._sidebar.setStyleSheet(
            "QListWidget { background: rgba(20, 24, 32, 0.45); color: #ccc; border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 6px; }"
            "QListWidget::item { padding: 6px 10px; color: #ccc; border-radius: 4px; }"
            "QListWidget::item:selected { background: #5865f2; color: #fff; }"
            "QListWidget::item:hover { background: rgba(255, 255, 255, 0.08); }"
        )
        self._populate_sidebar()
        self._sidebar.itemClicked.connect(
            lambda item: self._navigate(item.data(Qt.ItemDataRole.UserRole))
        )
        self._sidebar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._sidebar.customContextMenuRequested.connect(self._on_sidebar_context_menu)
        splitter.addWidget(self._sidebar)

        self._grid = QListWidget()
        self._grid.setViewMode(QListWidget.ViewMode.IconMode)
        self._grid.setIconSize(QSize(self._thumb_size, self._thumb_size))
        self._grid.setGridSize(QSize(self._thumb_size + 30, self._thumb_size + 40))
        self._grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._grid.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
            if self._single_selection
            else QListWidget.SelectionMode.ExtendedSelection
        )
        self._grid.setMovement(QListWidget.Movement.Static)
        self._grid.setWrapping(True)
        self._grid.setWordWrap(True)
        self._grid.setSpacing(8)
        self._grid.setFrameShape(QListWidget.Shape.NoFrame)
        self._grid.setStyleSheet(
            "QListWidget { background: rgba(14, 18, 25, 0.35); color: #ccc; border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 6px; }"
            "QListWidget::item { color: #ccc; border-radius: 6px; padding: 4px; border: 1px solid transparent; }"
            "QListWidget::item:selected { background: rgba(88, 101, 242, 0.35); border: 1px solid #5865f2; color: #fff; }"
            "QListWidget::item:hover { background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.2); }"
        )
        self._grid.itemDoubleClicked.connect(self._on_double_click)
        self._grid.itemSelectionChanged.connect(self._update_status)
        self._grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._grid.customContextMenuRequested.connect(self._on_grid_context_menu)
        splitter.addWidget(self._grid)
        splitter.setSizes([160, 780])
        splitter.setStretchFactor(1, 1)

        if persist_splitter:
            persist_splitter(splitter, "ThumbnailFilePicker/sidebar")
        layout.addWidget(splitter)

        # Bottom bar
        bottom = QHBoxLayout()
        self._status_label = QLabel("No files selected")

        size_lbl = QLabel("Thumbnail size:")
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(64, 256)
        self._size_slider.setValue(self._thumb_size)
        self._size_slider.setFixedWidth(120)
        self._size_slider.valueChanged.connect(self._on_size_changed)

        btn_open = QPushButton("Open")
        btn_open.setDefault(True)
        btn_open.clicked.connect(self._accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        bottom.addWidget(self._status_label)
        bottom.addStretch()
        bottom.addWidget(size_lbl)
        bottom.addWidget(self._size_slider)
        bottom.addWidget(btn_open)
        bottom.addWidget(btn_cancel)
        layout.addLayout(bottom)

    def _populate_sidebar(self) -> None:
        self._sidebar.clear()
        home = os.path.expanduser("~")
        bookmarks = [
            ("🏠 Home", home),
            ("🖥 Desktop", os.path.join(home, "Desktop")),
            ("🖼 Pictures", os.path.join(home, "Pictures")),
            ("📥 Downloads", os.path.join(home, "Downloads")),
            ("📄 Documents", os.path.join(home, "Documents")),
        ]
        favs = AppSettings.favourite_directories() if AppSettings else []
        norm_std = {os.path.normpath(p) for _, p in bookmarks if p}
        for fav_path in favs:
            if fav_path and os.path.isdir(fav_path):
                norm_fav = os.path.normpath(fav_path)
                if norm_fav not in norm_std:
                    label = f"⭐ {os.path.basename(norm_fav) or norm_fav}"
                    bookmarks.append((label, norm_fav))

        for label, path in bookmarks:
            if os.path.isdir(path):
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, path)
                self._sidebar.addItem(item)

    def _apply_menu_style(self, menu: QMenu) -> None:
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(28, 32, 42, 0.95);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #5865f2;
                color: white;
            }
        """)

    def _on_sidebar_context_menu(self, pos) -> None:
        item = self._sidebar.itemAt(pos)
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path or not os.path.isdir(path):
            return

        favs = AppSettings.favourite_directories() if AppSettings else []
        norm_path = os.path.normpath(path)
        norm_favs = [os.path.normpath(f) for f in favs]
        is_fav = norm_path in norm_favs

        menu = QMenu(self._sidebar)
        self._apply_menu_style(menu)
        fav_act = (
            QAction("❌ Remove from Favourites", menu)
            if is_fav
            else QAction("⭐ Add to Favourites", menu)
        )
        menu.addAction(fav_act)

        act = menu.exec(self._sidebar.mapToGlobal(pos))
        if act == fav_act:
            if is_fav:
                new_favs = [f for f in favs if os.path.normpath(f) != norm_path]
                if AppSettings:
                    AppSettings.set_favourite_directories(new_favs)
            else:
                favs.append(path)
                if AppSettings:
                    AppSettings.set_favourite_directories(favs)
            self._populate_sidebar()

    def _on_grid_context_menu(self, pos) -> None:
        item = self._grid.itemAt(pos)
        if item and item.data(Qt.ItemDataRole.UserRole + 1) == "dir":
            path = item.data(Qt.ItemDataRole.UserRole)
        else:
            path = self._current_dir

        if not path or not os.path.isdir(path):
            return

        favs = AppSettings.favourite_directories() if AppSettings else []
        norm_path = os.path.normpath(path)
        norm_favs = [os.path.normpath(f) for f in favs]
        is_fav = norm_path in norm_favs

        menu = QMenu(self._grid)
        self._apply_menu_style(menu)
        fav_act = (
            QAction("❌ Remove from Favourites", menu)
            if is_fav
            else QAction("⭐ Add to Favourites", menu)
        )
        menu.addAction(fav_act)

        act = menu.exec(self._grid.mapToGlobal(pos))
        if act == fav_act:
            if is_fav:
                new_favs = [f for f in favs if os.path.normpath(f) != norm_path]
                if AppSettings:
                    AppSettings.set_favourite_directories(new_favs)
            else:
                favs.append(path)
                if AppSettings:
                    AppSettings.set_favourite_directories(favs)
            self._populate_sidebar()

    def _navigate(self, path: str) -> None:
        path = os.path.normpath(path)
        if not os.path.isdir(path):
            return
        self._generation += 1
        gen = self._generation
        self._grid.clear()
        self._item_map.clear()
        self._current_dir = path
        self._addr_bar.setText(path)

        try:
            entries = sorted(
                os.scandir(path),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            return

        for entry in entries:
            if entry.is_dir() and not entry.name.startswith("."):
                item = QListWidgetItem(self._folder_icon, entry.name)
                item.setData(Qt.ItemDataRole.UserRole, entry.path)
                item.setData(Qt.ItemDataRole.UserRole + 1, "dir")
                self._grid.addItem(item)
            elif os.path.splitext(entry.name)[1].lower() in self._exts:
                item = QListWidgetItem(entry.name)
                item.setData(Qt.ItemDataRole.UserRole, entry.path)
                item.setData(Qt.ItemDataRole.UserRole + 1, "file")
                self._grid.addItem(item)
                self._item_map[entry.path] = item
                self._pool.start(
                    _ThumbTask(entry.path, self._thumb_size, gen, self._hub)
                )

        self._update_status()

    @Slot(str, int, object)
    def _on_thumb_loaded(self, path: str, generation: int, img: QImage) -> None:
        if generation != self._generation:
            return
        item = self._item_map.get(path)
        if item and not img.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    def _on_double_click(self, item: QListWidgetItem) -> None:
        if item.data(Qt.ItemDataRole.UserRole + 1) == "dir":
            self._navigate(item.data(Qt.ItemDataRole.UserRole))
        elif item.data(Qt.ItemDataRole.UserRole + 1) == "file":
            self._selected_paths = [item.data(Qt.ItemDataRole.UserRole)]
            self.accept()

    def _go_up(self) -> None:
        parent = os.path.dirname(self._current_dir)
        if parent != self._current_dir:
            self._navigate(parent)

    def _update_status(self) -> None:
        selected_files = [
            it.data(Qt.ItemDataRole.UserRole)
            for it in self._grid.selectedItems()
            if it.data(Qt.ItemDataRole.UserRole + 1) == "file"
        ]
        n = len(selected_files)
        if n == 0:
            self._status_label.setText("No files selected")
        elif n == 1:
            try:
                size_mb = os.path.getsize(selected_files[0]) / (1024 * 1024)
                self._status_label.setText(f"1 file selected ({os.path.basename(selected_files[0])} • {size_mb:.2f} MB)")
            except Exception:
                self._status_label.setText("1 file selected")
        else:
            self._status_label.setText(f"{n} files selected")

    def _on_size_changed(self, value: int) -> None:
        self._thumb_size = value
        self._grid.setIconSize(QSize(value, value))
        self._grid.setGridSize(QSize(value + 30, value + 40))
        self._navigate(self._current_dir)

    def _accept(self) -> None:
        self._selected_paths = [
            it.data(Qt.ItemDataRole.UserRole)
            for it in self._grid.selectedItems()
            if it.data(Qt.ItemDataRole.UserRole + 1) == "file"
        ]
        if self._selected_paths:
            self.accept()

    def selected_paths(self) -> list[str]:
        return self._selected_paths

    def selected_path(self) -> str:
        return self._selected_paths[0] if self._selected_paths else ""

    @staticmethod
    def getOpenFileName(
        parent: Optional[QWidget] = None,
        caption: str = "Select Image",
        start_dir: str = "",
        filter_exts: Optional[Sequence[str]] = None,
    ) -> tuple[str, str]:
        """Convenience function matching QFileDialog.getOpenFileName semantics."""
        dialog = ThumbnailFilePicker(
            parent=parent,
            caption=caption,
            start_dir=start_dir,
            filter_exts=filter_exts,
            single_selection=True,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            path = dialog.selected_path()
            return path, "Images"
        return "", ""

    @staticmethod
    def getOpenFileNames(
        parent: Optional[QWidget] = None,
        caption: str = "Select Images",
        start_dir: str = "",
        filter_exts: Optional[Sequence[str]] = None,
    ) -> tuple[list[str], str]:
        """Convenience function matching QFileDialog.getOpenFileNames semantics."""
        dialog = ThumbnailFilePicker(
            parent=parent,
            caption=caption,
            start_dir=start_dir,
            filter_exts=filter_exts,
            single_selection=False,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_paths(), "Images"
        return [], ""

    @staticmethod
    def _make_folder_icon(size: int = 64) -> QIcon:
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        amber = QColor(240, 185, 60)
        dark_amber = QColor(200, 145, 20)
        p.setPen(QPen(dark_amber, 1))
        p.setBrush(QBrush(amber))
        tab_h = size // 8
        body_top = size // 4
        p.drawRoundedRect(2, body_top, size // 3, tab_h, 3, 3)
        p.drawRoundedRect(
            2, body_top + tab_h - 2, size - 4, size - body_top - tab_h - 2, 5, 5
        )
        p.end()
        return QIcon(pm)


__all__ = ["ThumbnailFilePicker"]
