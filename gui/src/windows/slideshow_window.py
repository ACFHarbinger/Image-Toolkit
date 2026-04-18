from pathlib import Path
from typing import List, Dict, Optional
from PySide6.QtGui import QPixmap, QIcon, QImage
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
    item_swap_requested = Signal(
        str, int, str, int
    )  # src_mid, src_idx, target_mid, target_idx

    def __init__(
        self,
        monitor_name: str,
        monitor_id: str,
        queue: List[str],
        pixmap_cache: Optional[Dict[str, QPixmap]] = None,
        other_queues: Optional[Dict[str, List[str]]] = None,
        other_names: Optional[Dict[str, str]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.monitor_name = monitor_name
        self.monitor_id = monitor_id
        self.pixmap_cache = pixmap_cache if pixmap_cache is not None else {}
        self.other_queues = other_queues if other_queues is not None else {}
        self.other_names = other_names if other_names is not None else {}

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

    def _resolve_pixmap(self, path: str) -> Optional[QPixmap]:
        """Get a thumbnail from the cache, converting QImage to QPixmap if needed."""
        raw = self.pixmap_cache.get(path)
        if raw is None:
            return None
        return QPixmap.fromImage(raw) if isinstance(raw, QImage) else raw

    def populate_list(self, queue: List[str]):
        """Clears and repopulates the QListWidget with custom items, using cache for videos."""
        self.list_widget.clear()

        for idx, path in enumerate(queue, start=1):
            # 1. Try Cache First (Crucial for Video Thumbnails)
            pixmap = self._resolve_pixmap(path)

            # 2. Fallback to loading from file
            if not pixmap or pixmap.isNull():
                pixmap = QPixmap(path)

            # 3. Final Fallback placeholder
            if pixmap.isNull():
                pixmap = QPixmap(80, 60)
                pixmap.fill(Qt.darkGray)

            item_widget = QueueItemWidget(path, pixmap, index=idx)

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

        # --- SWAP SUB-MENU ---
        swap_menu = menu.addMenu(
            QIcon(QApplication.style().standardIcon(QStyle.SP_CommandLink)),
            "Swap with...",
        )

        # 1. Swap within this queue
        this_queue_menu = swap_menu.addMenu("This Queue")
        any_other_in_this = False
        for i in range(self.list_widget.count()):
            if i == current_row:
                continue
            any_other_in_this = True
            other_item = self.list_widget.item(i)
            filename = Path(other_item.data(Qt.UserRole)).name
            action = this_queue_menu.addAction(f"Item {i + 1}: {filename[:30]}...")
            action.triggered.connect(
                lambda _,
                src_idx=current_row,
                target_idx=i: self.item_swap_requested.emit(
                    self.monitor_id, src_idx, self.monitor_id, target_idx
                )
            )
        if not any_other_in_this:
            this_queue_menu.setEnabled(False)

        # 2. Swap with other monitors
        other_mon_added = False
        for mid, queue in self.other_queues.items():
            if mid == self.monitor_id:
                continue
            other_mon_added = True
            mon_name = self.other_names.get(mid, f"Monitor {mid}")
            mon_menu = swap_menu.addMenu(mon_name)
            if not queue:
                mon_menu.addAction("No items").setEnabled(False)
            else:
                for idx, path in enumerate(queue):
                    filename = Path(path).name
                    action = mon_menu.addAction(f"Item {idx + 1}: {filename[:30]}...")
                    action.triggered.connect(
                        lambda _,
                        src_idx=current_row,
                        t_mid=mid,
                        t_idx=idx: self.item_swap_requested.emit(
                            self.monitor_id, src_idx, t_mid, t_idx
                        )
                    )
        if not other_mon_added:
            swap_menu.setEnabled(any_other_in_this)

        menu.addSeparator()

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

    def refresh_indices(self):
        """Update indices for all widgets in the list."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if isinstance(widget, QueueItemWidget):
                widget.update_index(i + 1)

    @Slot(QListWidgetItem)
    def move_item_up(self, item: QListWidgetItem):
        current_row = self.list_widget.row(item)
        if current_row > 0:
            path = item.data(Qt.UserRole)
            self.list_widget.takeItem(current_row)

            # Recreate widget
            pixmap = self._resolve_pixmap(path)
            if not pixmap or pixmap.isNull():
                pixmap = QPixmap(path)
                if pixmap.isNull():
                    pixmap = QPixmap(80, 60)
                    pixmap.fill(Qt.darkGray)

            new_widget = QueueItemWidget(path, pixmap, index=current_row)
            new_item = QListWidgetItem()
            new_item.setData(Qt.UserRole, path)
            new_item.setSizeHint(new_widget.sizeHint())

            self.list_widget.insertItem(current_row - 1, new_item)
            self.list_widget.setItemWidget(new_item, new_widget)
            self.list_widget.setCurrentItem(new_item)
            self.refresh_indices()
            self.emit_new_queue_order()

    @Slot(QListWidgetItem)
    def move_item_down(self, item: QListWidgetItem):
        current_row = self.list_widget.row(item)
        if current_row < self.list_widget.count() - 1:
            path = item.data(Qt.UserRole)
            self.list_widget.takeItem(current_row)

            # Recreate widget
            pixmap = self._resolve_pixmap(path)
            if not pixmap or pixmap.isNull():
                pixmap = QPixmap(path)
                if pixmap.isNull():
                    pixmap = QPixmap(80, 60)
                    pixmap.fill(Qt.darkGray)

            new_widget = QueueItemWidget(path, pixmap, index=current_row + 2)
            new_item = QListWidgetItem()
            new_item.setData(Qt.UserRole, path)
            new_item.setSizeHint(new_widget.sizeHint())

            self.list_widget.insertItem(current_row + 1, new_item)
            self.list_widget.setItemWidget(new_item, new_widget)
            self.list_widget.setCurrentItem(new_item)
            self.refresh_indices()
            self.emit_new_queue_order()

    @Slot(QListWidgetItem)
    def remove_item(self, item: QListWidgetItem):
        current_row = self.list_widget.row(item)
        self.list_widget.takeItem(current_row)
        self.refresh_indices()
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

        self.refresh_indices()
        self.queue_reordered.emit(self.monitor_id, new_queue)
