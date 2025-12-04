from typing import List, Dict, Optional
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt, Slot, QPoint, Signal
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QListWidget,
    QMenu,
    QListWidgetItem,
    QApplication,
    QStyle,
)
from ..components import QueueItemWidget


class SlideshowQueueWindow(QWidget):
    """A window that displays a re-orderable list of image previews."""

    queue_reordered = Signal(str, list)
    image_preview_requested = Signal(str)

    # Updated Init to accept pixmap_cache
    def __init__(
        self,
        monitor_name: str,
        monitor_id: str,
        queue: List[str],
        pixmap_cache: Optional[Dict[str, QPixmap]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.monitor_name = monitor_name
        self.monitor_id = monitor_id
        self.pixmap_cache = pixmap_cache if pixmap_cache is not None else {}

        self.setWindowTitle(f"Queue for {monitor_name}")
        self.setMinimumSize(400, 500)

        layout = QVBoxLayout(self)

        title_label = QLabel(
            f"Queue: {len(queue)} Images (Drag or Right-click to modify)"
        )
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(title_label)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { border: 1px solid #4f545c; border-radius: 8px; }"
        )

        self.list_widget.setDragDropMode(QListWidget.InternalMove)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)

        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.itemDoubleClicked.connect(self.handle_list_item_action)

        self.populate_list(queue)

        layout.addWidget(self.list_widget)
        self.list_widget.model().rowsMoved.connect(self.emit_new_queue_order)
        self.setLayout(layout)

    def populate_list(self, queue: List[str]):
        """Clears and repopulates the QListWidget with custom items, using cache for videos."""
        self.list_widget.clear()

        for path in queue:
            # 1. Try Cache First (Crucial for Video Thumbnails)
            pixmap = self.pixmap_cache.get(path)

            # 2. Fallback to loading from file
            if not pixmap or pixmap.isNull():
                pixmap = QPixmap(path)

            # 3. Final Fallback placeholder
            if pixmap.isNull():
                pixmap = QPixmap(80, 60)
                pixmap.fill(Qt.darkGray)

            item_widget = QueueItemWidget(path, pixmap)

            list_item = QListWidgetItem(self.list_widget)
            list_item.setSizeHint(item_widget.sizeHint())
            list_item.setData(Qt.UserRole, path)

            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, item_widget)

    # ... (Rest of the class methods: handle_list_item_action, show_context_menu, etc. remain unchanged)
    @Slot(QListWidgetItem)
    def handle_list_item_action(self, item: QListWidgetItem):
        if item:
            file_path = item.data(Qt.UserRole)
            if file_path:
                self.image_preview_requested.emit(file_path)

    @Slot(QPoint)
    def show_context_menu(self, pos: QPoint):
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        self.list_widget.setCurrentItem(item)
        current_row = self.list_widget.row(item)

        menu = QMenu(self)
        move_up_action = menu.addAction(
            QIcon(QApplication.style().standardIcon(QStyle.SP_ArrowUp)), "Move Up"
        )
        move_down_action = menu.addAction(
            QIcon(QApplication.style().standardIcon(QStyle.SP_ArrowDown)), "Move Down"
        )
        view_action = menu.addAction(
            QIcon(QApplication.style().standardIcon(QStyle.SP_FileIcon)),
            "View Full Image",
        )
        menu.addSeparator()
        remove_action = menu.addAction(
            QIcon(QApplication.style().standardIcon(QStyle.SP_DialogCancelButton)),
            "Remove from Queue",
        )

        move_up_action.triggered.connect(lambda: self.move_item_up(item))
        move_down_action.triggered.connect(lambda: self.move_item_down(item))
        view_action.triggered.connect(lambda: self.handle_list_item_action(item))
        remove_action.triggered.connect(lambda: self.remove_item(item))

        if current_row == 0:
            move_up_action.setEnabled(False)
        if current_row == self.list_widget.count() - 1:
            move_down_action.setEnabled(False)

        menu.exec(self.list_widget.mapToGlobal(pos))

    @Slot(QListWidgetItem)
    def move_item_up(self, item: QListWidgetItem):
        current_row = self.list_widget.row(item)
        if current_row > 0:
            widget = self.list_widget.itemWidget(item)
            taken_item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row - 1, taken_item)
            self.list_widget.setItemWidget(taken_item, widget)
            taken_item.setSizeHint(widget.sizeHint())
            self.list_widget.setCurrentItem(taken_item)
            self.emit_new_queue_order()

    @Slot(QListWidgetItem)
    def move_item_down(self, item: QListWidgetItem):
        current_row = self.list_widget.row(item)
        if current_row < self.list_widget.count() - 1:
            widget = self.list_widget.itemWidget(item)
            taken_item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row + 1, taken_item)
            self.list_widget.setItemWidget(taken_item, widget)
            taken_item.setSizeHint(widget.sizeHint())
            self.list_widget.setCurrentItem(taken_item)
            self.emit_new_queue_order()

    @Slot(QListWidgetItem)
    def remove_item(self, item: QListWidgetItem):
        current_row = self.list_widget.row(item)
        self.list_widget.takeItem(current_row)
        self.emit_new_queue_order()

    @Slot()
    def emit_new_queue_order(self, *args):
        new_queue = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            new_queue.append(item.data(Qt.UserRole))

        title_label = self.findChild(QLabel)
        if title_label:
            title_label.setText(
                f"Queue: {len(new_queue)} Images (Drag or Right-click to modify)"
            )

        self.queue_reordered.emit(self.monitor_id, new_queue)
