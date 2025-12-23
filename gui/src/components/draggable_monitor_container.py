from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QLayout, QSizePolicy
from .monitor_drop_widget import MonitorDropWidget


class DraggableMonitorContainer(QWidget):
    """
    A Custom Container that accepts MonitorDropWidget drops and reorders them.
    Supports a 2D grid layout (rows of horizontal layouts).
    """

    def __init__(self, monitor=None, monitor_id=None, parent=None):
        super().__init__(parent)
        self.monitor = monitor
        self.monitor_id = monitor_id
        
        # Main layout is Vertical (Rows)
        self.layout_vbox = QVBoxLayout(self)
        self.layout_vbox.setSpacing(15)
        self.layout_vbox.setAlignment(Qt.AlignTop)
        
        # Internal state: list of lists of widgets [[w1, w2], [w3]]
        self.rows = [] 
        
        # Initialize with one empty row
        self._add_new_row()
        
        self.setAcceptDrops(True)

    def _add_new_row(self):
        row_widget = QWidget()
        row_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(15)
        row_layout.setAlignment(Qt.AlignCenter)
        
        self.layout_vbox.addWidget(row_widget)
        self.rows.append([])
        
        return row_widget, row_layout

    def text(self) -> str:
        if self.monitor is not None:
            return f"{self.monitor.name}"
        return ""

    def addWidget(self, widget):
        """Adds a widget to the last row, creating a new one if needed (not actually used much in this logic except init)."""
        if not self.rows:
            self._add_new_row()
        
        # Add to the last row's layout
        last_row_index = len(self.rows) - 1
        self._get_row_layout(last_row_index).addWidget(widget)
        self.rows[last_row_index].append(widget)

    def _get_row_layout(self, index) -> QHBoxLayout:
        if 0 <= index < self.layout_vbox.count():
            return self.layout_vbox.itemAt(index).widget().layout()
        return None

    def dragEnterEvent(self, event):
        if event.source() and isinstance(event.source(), MonitorDropWidget):
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.source() and isinstance(event.source(), MonitorDropWidget):
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        source = event.source()
        if isinstance(source, MonitorDropWidget):
            pos = event.position().toPoint()
            
            # 1. Remove source from its current position in self.rows
            source_removed = False
            for r_idx, row in enumerate(self.rows):
                if source in row:
                    row.remove(source)
                    # Remove from layout
                    self._get_row_layout(r_idx).removeWidget(source)
                    source_removed = True
                    break
            
            # 2. Determine drop target
            target_row_idx = -1
            target_col_idx = -1
            insert_new_row_above = False
            insert_new_row_below = False

            # Vertical Hit Testing (Zones: Top 10%, Middle 80%, Bottom 10%)
            ZONE_RATIO = 0.10

            found_row = False
            for r_idx in range(self.layout_vbox.count()):
                item = self.layout_vbox.itemAt(r_idx)
                if not item or not item.widget():
                    continue
                    
                row_widget = item.widget()
                row_rect = row_widget.geometry()
                row_height = row_rect.height()
                
                # Check if strictly inside this row's vertical range
                if row_rect.top() <= pos.y() <= row_rect.bottom():
                    target_row_idx = r_idx
                    found_row = True
                    
                    # Check vertical zones within this row
                    if pos.y() < row_rect.top() + (row_height * ZONE_RATIO):
                        insert_new_row_above = True
                    elif pos.y() > row_rect.bottom() - (row_height * ZONE_RATIO):
                        insert_new_row_below = True
                    else:
                        # Find horizontal position (Merge)
                        row_layout = row_widget.layout()
                        count = row_layout.count()
                        target_col_idx = count
                        
                        for i in range(count):
                            item = row_layout.itemAt(i)
                            w = item.widget()
                            if w:
                                w_center = w.x() + (row_widget.x()) + (w.width() / 2)
                                if pos.x() < w_center:
                                    target_col_idx = i
                                    break
                    break

            # If not inside any row, check if it's above/below the entire stack
            if not found_row:
                if self.layout_vbox.count() > 0:
                    first_row = self.layout_vbox.itemAt(0).widget().geometry()
                    last_row = self.layout_vbox.itemAt(self.layout_vbox.count() - 1).widget().geometry()
                    
                    if pos.y() < first_row.top():
                        target_row_idx = 0
                        insert_new_row_above = True
                    elif pos.y() > last_row.bottom():
                        target_row_idx = self.layout_vbox.count() - 1
                        insert_new_row_below = True
                    else:
                        # It's between rows in the spacing. 
                        # Find which row it's below.
                        for r_idx in range(self.layout_vbox.count() - 1):
                            r1 = self.layout_vbox.itemAt(r_idx).widget().geometry()
                            r2 = self.layout_vbox.itemAt(r_idx + 1).widget().geometry()
                            if r1.bottom() < pos.y() < r2.top():
                                target_row_idx = r_idx
                                insert_new_row_below = True
                                break
            
            # Handle Drop Logic
            
            if insert_new_row_above:
                # Insert a new empty row at target_row_idx
                new_row_widget = QWidget()
                new_row_layout = QHBoxLayout(new_row_widget)
                new_row_layout.setContentsMargins(0,0,0,0)
                new_row_layout.setSpacing(15)
                new_row_layout.setAlignment(Qt.AlignCenter)
                
                self.layout_vbox.insertWidget(target_row_idx, new_row_widget)
                self.rows.insert(target_row_idx, [source])
                new_row_layout.addWidget(source)
                
            elif insert_new_row_below:
                # Insert a new empty row at target_row_idx + 1
                new_idx = target_row_idx + 1
                new_row_widget = QWidget()
                new_row_layout = QHBoxLayout(new_row_widget)
                new_row_layout.setContentsMargins(0,0,0,0)
                new_row_layout.setSpacing(15)
                new_row_layout.setAlignment(Qt.AlignCenter)
                
                self.layout_vbox.insertWidget(new_idx, new_row_widget)
                self.rows.insert(new_idx, [source])
                new_row_layout.addWidget(source)
                
            elif target_row_idx != -1:
                # Insert into existing row
                if target_row_idx >= len(self.rows):
                    # Should not happen if logic is correct, but safety:
                    self.rows.append([source])
                    self._get_row_layout(len(self.rows)-1).addWidget(source)
                else:
                    self.rows[target_row_idx].insert(target_col_idx, source)
                    self._get_row_layout(target_row_idx).insertWidget(target_col_idx, source)
                    
            else:
                # Dropped in empty space (e.g. very bottom) -> New Row at end
                self._add_new_row()
                last_idx = len(self.rows) - 1
                self.rows[last_idx].append(source)
                self._get_row_layout(last_idx).addWidget(source)

            # Cleanup empty rows
            self._cleanup_empty_rows()

            event.accept()
            self.update()
        else:
            # Pass to parent (though we accepted drag, so maybe not? Standard pattern says super if not handled)
            super().dropEvent(event)

    def _cleanup_empty_rows(self):
        """Remove any rows that have no widgets."""
        rows_to_remove = []
        for i, row in enumerate(self.rows):
            if not row:
                rows_to_remove.append(i)
        
        # Remove in reverse order to maintain indices
        for i in reversed(rows_to_remove):
            # Remove from data
            self.rows.pop(i)
            # Remove from layout
            item = self.layout_vbox.takeAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        
        # Ensure at least one row exists if empty?
        if not self.rows:
            self._add_new_row()

    def clear_widgets(self):
        """Clear all widgets and rows."""
        self.rows = []
        while self.layout_vbox.count():
            item = self.layout_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Re-init default state
        self._add_new_row()
