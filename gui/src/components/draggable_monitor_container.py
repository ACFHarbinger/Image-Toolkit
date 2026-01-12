from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QSizePolicy
from .monitor_drop_widget import MonitorDropWidget


class MonitorColumn(QWidget):
    """
    A vertical column that can hold multiple MonitorDropWidgets.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_vbox = QVBoxLayout(self)
        self.layout_vbox.setContentsMargins(0, 0, 0, 0)
        self.layout_vbox.setSpacing(10)
        self.layout_vbox.setAlignment(Qt.AlignTop)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)

    def add_monitor(self, widget: MonitorDropWidget):
        self.layout_vbox.addWidget(widget)
        # Adjust width to match the widget
        self.setFixedWidth(widget.width())

    def insert_monitor(self, index: int, widget: MonitorDropWidget):
        self.layout_vbox.insertWidget(index, widget)
        self.setFixedWidth(widget.width())

    def remove_monitor(self, widget: MonitorDropWidget):
        self.layout_vbox.removeWidget(widget)
        if self.layout_vbox.count() == 0:
            self.setFixedWidth(0)

    def count(self):
        return self.layout_vbox.count()

    def widget_at(self, index):
        item = self.layout_vbox.itemAt(index)
        if item:
            return item.widget()
        return None

    def get_widgets(self):
        widgets = []
        for i in range(self.layout_vbox.count()):
            item = self.layout_vbox.itemAt(i)
            if item and item.widget():
                widgets.append(item.widget())
        return widgets


class DraggableMonitorContainer(QWidget):
    """
    A Custom Container that accepts MonitorDropWidget drops and reorders them.
    Supports a grid-like layout where:
    - Main layout is Vertical (Rows).
    - Each Row is Horizontal (Columns).
    - Each Column is Vertical (Stack of MonitorDropWidgets).
    """

    def __init__(self, monitor=None, monitor_id=None, parent=None):
        super().__init__(parent)
        self.monitor = monitor
        self.monitor_id = monitor_id

        # Main layout is Vertical (Rows)
        self.layout_vbox = QVBoxLayout(self)
        self.layout_vbox.setSpacing(20)
        self.layout_vbox.setAlignment(Qt.AlignTop)

        # Keep track of rows (widgets)
        # self.rows = [] # Not strictly needed if we inspect layout, but good for logic.

        # Initialize with one empty row
        self._add_new_row()

        self.setAcceptDrops(True)

    def _add_new_row(self, index=-1):
        row_widget = QWidget()
        row_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(20)
        row_layout.setAlignment(Qt.AlignCenter)

        if index == -1:
            self.layout_vbox.addWidget(row_widget)
        else:
            self.layout_vbox.insertWidget(index, row_widget)

        return row_widget

    def text(self) -> str:
        if self.monitor is not None:
            return f"{self.monitor.name}"
        return ""

    def addWidget(self, widget: MonitorDropWidget):
        """Adds a widget to the last row, in a new column."""
        # Find last row
        count = self.layout_vbox.count()
        if count == 0:
            self._add_new_row()
            count = 1

        last_row = self.layout_vbox.itemAt(count - 1).widget()

        # Create a new column
        col = MonitorColumn()
        col.add_monitor(widget)

        last_row.layout().addWidget(col)

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
        if not isinstance(source, MonitorDropWidget):
            super().dropEvent(event)
            return

        pos = event.position().toPoint()

        # 1. Detach source from its current parent
        # We need to find its current column and remove it
        self._detach_widget(source)

        # 2. Find drop target
        # Strategy: Use childAt to find if we are over a specific MonitorDropWidget
        target_child = self.childAt(pos)

        # childAt matches the deepest child, might be a label inside or the widget itself.
        # Walk up until we find a MonitorDropWidget or MonitorColumn or Row
        target_monitor_widget = None
        current = target_child
        while current and current != self:
            if isinstance(current, MonitorDropWidget):
                target_monitor_widget = current
                break
            current = current.parentWidget()

        if target_monitor_widget:
            # We dropped ONTOP of a monitor widget. Determine quadrant.
            # Local coordinates within the target widget
            local_pos = target_monitor_widget.mapFrom(self, pos)
            w = target_monitor_widget.width()
            h = target_monitor_widget.height()

            # Zones
            # Top 25%: stack above
            # Bottom 25%: stack below
            # Left 25%: new column left
            # Right 25%: new column right

            # We prioritize vertical stacking if in middle 50% X?
            # Or just strict zones?

            # Let's use simple logic:
            # If y < h*0.25 -> Top
            # If y > h*0.75 -> Bottom
            # Else:
            #   If x < w*0.5 -> Left
            #   Else -> Right

            target_col = target_monitor_widget.parentWidget()  # Should be MonitorColumn
            if not isinstance(target_col, MonitorColumn):
                # Fallback, shouldn't happen
                self._append_to_end(source)
                return

            if local_pos.y() < h * 0.25:
                # Top
                idx = target_col.layout_vbox.indexOf(target_monitor_widget)
                target_col.insert_monitor(idx, source)

            elif local_pos.y() > h * 0.75:
                # Bottom
                idx = target_col.layout_vbox.indexOf(target_monitor_widget)
                target_col.insert_monitor(idx + 1, source)

            else:
                # Left or Right - New Column
                target_row = target_col.parentWidget()  # Should be Row (QWidget)
                row_layout = target_row.layout()
                col_idx = row_layout.indexOf(target_col)

                new_col = MonitorColumn()
                new_col.add_monitor(source)

                if local_pos.x() < w * 0.5:
                    # Left
                    row_layout.insertWidget(col_idx, new_col)
                else:
                    # Right
                    row_layout.insertWidget(col_idx + 1, new_col)

        else:
            # Dropped in empty space
            # Check if we are in a row's horizontal space (between columns)
            # or between rows (vertical space)

            # Find closest row vertically
            drop_y = pos.y()
            best_row_idx = -1
            best_row_dist = 999999

            for i in range(self.layout_vbox.count()):
                item = self.layout_vbox.itemAt(i)
                w = item.widget()
                if not w:
                    continue

                r_geo = w.geometry()

                # Check if inside row vertically
                if r_geo.top() <= drop_y <= r_geo.bottom():
                    best_row_idx = i
                    break

                # Dist to center
                center_y = r_geo.center().y()
                dist = abs(center_y - drop_y)
                if dist < best_row_dist:
                    best_row_dist = dist
                    # Tentatively picking closest row, but need to check bounds for insert

            # If we didn't land INSIDE a row, check insertions
            inserted_row = False
            if best_row_idx != -1:
                # Check if we are legitimately inside the row rect
                row_w = self.layout_vbox.itemAt(best_row_idx).widget()
                if row_w.geometry().contains(pos):
                    # Inside row, between columns probably
                    # Find correct column index
                    # Just assume end for now unless we do complex distance calc
                    # Actually childAt should have caught it if we were over a widget.
                    # So we are in spacing.
                    # Let's just find closest column X
                    closest_col_idx = -1
                    last_x = -1
                    row_layout = row_w.layout()

                    for i in range(row_layout.count()):
                        col = row_layout.itemAt(i).widget()
                        if (
                            drop_y < col.geometry().top()
                            or drop_y > col.geometry().bottom()
                        ):
                            # If we are vastly outside the column vertical area, maybe we shouldn't merge?
                            pass

                        if pos.x() < col.geometry().center().x():
                            closest_col_idx = i
                            break

                    new_col = MonitorColumn()
                    new_col.add_monitor(source)

                    if closest_col_idx != -1:
                        row_layout.insertWidget(closest_col_idx, new_col)
                    else:
                        row_layout.addWidget(new_col)
                    inserted_row = True

            if not inserted_row:
                # Create new row
                # Find insertion index
                insert_idx = -1
                for i in range(self.layout_vbox.count()):
                    w = self.layout_vbox.itemAt(i).widget()
                    if drop_y < w.geometry().center().y():
                        insert_idx = i
                        break

                new_w = self._add_new_row(insert_idx if insert_idx != -1 else -1)

                new_col = MonitorColumn()
                new_col.add_monitor(source)
                new_w.layout().addWidget(new_col)

        self._cleanup()
        event.accept()
        self.update()

    def _detach_widget(self, widget: MonitorDropWidget):
        """Removes the widget from its current column. Does NOT delete it."""
        parent_col = widget.parentWidget()
        if isinstance(parent_col, MonitorColumn):
            parent_col.remove_monitor(widget)
            # parent_col.layout().removeWidget(widget) # Done in remove_monitor
            widget.setParent(None)  # Important to detach from layout system
            widget.show()  # Maintain visibility

    def _append_to_end(self, widget):
        self.addWidget(widget)

    def _cleanup(self):
        """Remove empty columns and rows."""
        # Cleanup Empty Columns
        rows_to_check = []
        for i in range(self.layout_vbox.count()):
            row = self.layout_vbox.itemAt(i).widget()
            rows_to_check.append(row)

        for row in rows_to_check:
            layout = row.layout()
            cols_to_remove = []
            for j in range(layout.count()):
                col = layout.itemAt(j).widget()
                if isinstance(col, MonitorColumn):
                    if col.count() == 0:
                        cols_to_remove.append(col)

            for col in cols_to_remove:
                layout.removeWidget(col)
                col.deleteLater()

        # Cleanup Empty Rows
        empty_rows = []
        for i in range(self.layout_vbox.count()):
            row = self.layout_vbox.itemAt(i).widget()
            if row.layout().count() == 0:
                empty_rows.append(row)

        for row in empty_rows:
            self.layout_vbox.removeWidget(row)
            row.deleteLater()

        # Ensure at least one row?
        if self.layout_vbox.count() == 0:
            self._add_new_row()

    @property
    def rows(self):
        """
        Backward compatibility for accessing rows of widgets.
        Returns a list of lists, where each inner list contains all MonitorDropWidgets
        in that visual row (aggregated from all columns).
        """
        result = []
        for i in range(self.layout_vbox.count()):
            row_widget = self.layout_vbox.itemAt(i).widget()
            if not row_widget:
                continue

            row_monitors = []
            row_layout = row_widget.layout()
            if not row_layout:
                continue

            for j in range(row_layout.count()):
                col_widget = row_layout.itemAt(j).widget()
                if isinstance(col_widget, MonitorColumn):
                    row_monitors.extend(col_widget.get_widgets())

            if row_monitors:
                result.append(row_monitors)
        return result

    def get_layout_structure(self) -> list:
        """
        Returns the current layout as a nested list:
        [
            [ # Row 1
                [MonitorID1, MonitorID2], # Col 1
                [MonitorID3],             # Col 2
            ],
            [ # Row 2
                ...
            ]
        ]
        """
        structure = []
        for i in range(self.layout_vbox.count()):
            row_widget = self.layout_vbox.itemAt(i).widget()
            if not row_widget:
                continue

            row_structure = []
            row_layout = row_widget.layout()
            if not row_layout:
                continue

            for j in range(row_layout.count()):
                col_widget = row_layout.itemAt(j).widget()
                if isinstance(col_widget, MonitorColumn):
                    col_monitor_ids = [w.monitor_id for w in col_widget.get_widgets()]
                    if col_monitor_ids:
                        row_structure.append(col_monitor_ids)

            if row_structure:
                structure.append(row_structure)
        return structure

    def set_layout_structure(self, structure: list, monitor_widgets_map: dict):
        """
        Reconstructs the layout from a structure list.
        monitor_widgets_map: Dict connecting monitor_id -> MonitorDropWidget
        """
        self.clear_widgets()

        used_monitor_ids = set()

        for row_data in structure:
            if not row_data:
                continue

            row_widget = self._add_new_row()
            row_layout = row_widget.layout()

            for col_data in row_data:
                if not col_data:
                    continue

                new_col = MonitorColumn()
                has_widgets = False
                for monitor_id in col_data:
                    if monitor_id in monitor_widgets_map:
                        widget = monitor_widgets_map[monitor_id]
                        new_col.add_monitor(widget)
                        used_monitor_ids.add(monitor_id)
                        has_widgets = True

                if has_widgets:
                    row_layout.addWidget(new_col)

            # If row ended up empty (e.g. monitors disconnected), cleanup?
            if row_layout.count() == 0:
                self.layout_vbox.removeWidget(row_widget)
                row_widget.deleteLater()

        # Handle orphaned monitors (connected but not in config)
        orphans = []
        for m_id, widget in monitor_widgets_map.items():
            if m_id not in used_monitor_ids:
                orphans.append(widget)

        if orphans:
            # Create a new row for orphans at the bottom
            orphan_row = self._add_new_row()
            # Spread them out or stack them? Let's spread them as single-item columns
            for widget in orphans:
                new_col = MonitorColumn()
                new_col.add_monitor(widget)
                orphan_row.layout().addWidget(new_col)

        self._cleanup()

    def clear_widgets(self):
        # Clear everything
        while self.layout_vbox.count():
            item = self.layout_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._add_new_row()
