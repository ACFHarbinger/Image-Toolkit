from typing import List
from pathlib import Path
from PySide6.QtCore import Qt, Slot, QPoint, Signal
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QListWidget, QListWidgetItem,
    QMenu, QMessageBox, QApplication, QStyle
)
from ..components import QueueItemWidget


class SlideshowQueueWindow(QWidget):
    """A window that displays a re-orderable list of image previews."""
    
    # Signal: (monitor_id, new_queue_list)
    queue_reordered = Signal(str, list)
    
    def __init__(self, monitor_name: str, monitor_id: str, queue: List[str], parent=None):
        super().__init__(parent)
        self.monitor_name = monitor_name
        self.monitor_id = monitor_id
        
        self.setWindowTitle(f"Queue for {monitor_name}")
        self.setMinimumSize(400, 500)
        
        layout = QVBoxLayout(self)
        
        # Title Label
        title_label = QLabel(f"Queue: {len(queue)} Images (Drag or Right-click to modify)")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(title_label)
        
        # The List Widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("QListWidget { border: 1px solid #4f545c; border-radius: 8px; }")
        
        # Enable Drag and Drop
        self.list_widget.setDragDropMode(QListWidget.InternalMove)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)
        
        # Enable Context Menu
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        # Populate the list with custom widgets
        self.populate_list(queue)
            
        layout.addWidget(self.list_widget)
        
        # Connect the model's signal for when rows are moved (Drag & Drop finished)
        self.list_widget.model().rowsMoved.connect(self.emit_new_queue_order)
        
        self.setLayout(layout)

    def populate_list(self, queue: List[str]):
        """Clears and repopulates the QListWidget with custom items."""
        self.list_widget.clear()
        
        for path in queue:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                pixmap = QPixmap(80, 60) # Placeholder
                pixmap.fill(Qt.darkGray)

            # NOTE: Assuming QueueItemWidget class is available
            item_widget = QueueItemWidget(path, pixmap)
            
            list_item = QListWidgetItem(self.list_widget)
            list_item.setSizeHint(item_widget.sizeHint())
            list_item.setData(Qt.UserRole, path)
            
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, item_widget)

    @Slot(QPoint)
    def show_context_menu(self, pos: QPoint):
        """Shows a context menu to move or remove the selected item."""
        # Get the item at the position where the right-click occurred
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        self.list_widget.setCurrentItem(item)
        current_row = self.list_widget.row(item)
        
        menu = QMenu(self)
        
        # Define Actions with standard icons
        move_up_action = menu.addAction(QIcon(QApplication.style().standardIcon(QStyle.SP_ArrowUp)), "Move Up")
        move_down_action = menu.addAction(QIcon(QApplication.style().standardIcon(QStyle.SP_ArrowDown)), "Move Down")
        menu.addSeparator()
        remove_action = menu.addAction(QIcon(QApplication.style().standardIcon(QStyle.SP_DialogCancelButton)), "Remove from Queue")
        
        # Connect actions using lambda to pass the item instance
        move_up_action.triggered.connect(lambda: self.move_item_up(item))
        move_down_action.triggered.connect(lambda: self.move_item_down(item))
        remove_action.triggered.connect(lambda: self.remove_item(item))
        
        # Disable actions based on position
        if current_row == 0:
            move_up_action.setEnabled(False)
        if current_row == self.list_widget.count() - 1:
            move_down_action.setEnabled(False)
            
        menu.exec(self.list_widget.mapToGlobal(pos))

    @Slot(QListWidgetItem)
    def move_item_up(self, item: QListWidgetItem):
        current_row = self.list_widget.row(item)
        if current_row > 0:
            # 1. Get the item's custom widget BEFORE removing the item
            widget = self.list_widget.itemWidget(item)
            
            # 2. Take the item out (this detaches the widget)
            taken_item = self.list_widget.takeItem(current_row)
            
            # 3. Re-insert the item one position higher
            new_row = current_row - 1
            self.list_widget.insertItem(new_row, taken_item)
            
            # 4. Re-associate the custom widget with the item
            self.list_widget.setItemWidget(taken_item, widget)
            
            # 5. NEW FIX: Re-apply the size hint to force a full layout re-evaluation
            taken_item.setSizeHint(widget.sizeHint())
            
            self.list_widget.setCurrentItem(taken_item)
            
            # 6. Process events and update the view
            QApplication.processEvents()
            self.list_widget.model().layoutChanged.emit() # Force model change signal
            
            self.emit_new_queue_order()

    @Slot(QListWidgetItem)
    def move_item_down(self, item: QListWidgetItem):
        current_row = self.list_widget.row(item)
        if current_row < self.list_widget.count() - 1:
            # 1. Get the item's custom widget BEFORE removing the item
            widget = self.list_widget.itemWidget(item)

            # 2. Take the item out (this detaches the widget)
            taken_item = self.list_widget.takeItem(current_row)
            
            # 3. Re-insert it one position lower
            new_row = current_row + 1
            self.list_widget.insertItem(new_row, taken_item)
            
            # 4. Re-associate the custom widget with the item
            self.list_widget.setItemWidget(taken_item, widget)
            
            # 5. NEW FIX: Re-apply the size hint to force a full layout re-evaluation
            taken_item.setSizeHint(widget.sizeHint())
            
            self.list_widget.setCurrentItem(taken_item)
            
            # 6. Process events and update the view
            QApplication.processEvents()
            self.list_widget.model().layoutChanged.emit() # Force model change signal
            
            self.emit_new_queue_order()

    @Slot(QListWidgetItem)
    def remove_item(self, item: QListWidgetItem):
        reply = QMessageBox.question(self, "Remove Image", 
                                     f"Are you sure you want to remove '{Path(item.data(Qt.UserRole)).name}' from this monitor's queue?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            current_row = self.list_widget.row(item)
            # Delete both the QListWidgetItem and its contents
            self.list_widget.takeItem(current_row) 
            self.emit_new_queue_order()

    @Slot()
    def emit_new_queue_order(self, *args): 
        """Helper to build and emit the new list order after drag/context menu action."""
        new_queue = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            # Ensure the list is built from the item's stored path data
            new_queue.append(item.data(Qt.UserRole))
        
        # Update the title
        title_label = self.findChild(QLabel)
        if title_label:
             title_label.setText(f"Queue: {len(new_queue)} Images (Drag or Right-click to modify)")
        
        # Emit the signal with the new path order
        self.queue_reordered.emit(self.monitor_id, new_queue)
