
import pytest
from PySide6.QtCore import Qt, QPoint, QMimeData
from PySide6.QtGui import QDrag, QMouseEvent, QDropEvent
from PySide6.QtWidgets import QWidget, QApplication
from gui.src.components.draggable_monitor_container import DraggableMonitorContainer, MonitorColumn
from gui.src.components.monitor_drop_widget import MonitorDropWidget

class MockMonitor:
    def __init__(self, name="TestMonitor", id="1"):
        self.name = name
        self.id = id

class TestMonitorColumnLogic:
    def test_default_structure(self, q_app):
        container = DraggableMonitorContainer()
        assert container.layout_vbox.count() == 1 # Initial empty row
        
        # Add 1 widget
        m1 = MockMonitor("M1", "1")
        w1 = MonitorDropWidget(m1, "1")
        container.addWidget(w1)
        
        # Structure should be: Row -> Column -> Widget
        row = container.layout_vbox.itemAt(0).widget()
        assert row.layout().count() == 1
        col = row.layout().itemAt(0).widget()
        assert isinstance(col, MonitorColumn)
        assert col.count() == 1
        assert col.widget_at(0) == w1

    def test_add_second_widget_new_column(self, q_app):
        container = DraggableMonitorContainer()
        w1 = MonitorDropWidget(MockMonitor("M1"), "1")
        w2 = MonitorDropWidget(MockMonitor("M2"), "2")
        
        container.addWidget(w1)
        container.addWidget(w2)
        
        row = container.layout_vbox.itemAt(0).widget()
        assert row.layout().count() == 2
        
        c1 = row.layout().itemAt(0).widget()
        c2 = row.layout().itemAt(1).widget()
        
        assert isinstance(c1, MonitorColumn)
        assert isinstance(c2, MonitorColumn)
        assert c1.widget_at(0) == w1
        assert c2.widget_at(0) == w2

    def test_column_helpers(self, q_app):
        col = MonitorColumn()
        w1 = MonitorDropWidget(MockMonitor("M1"), "1")
        w2 = MonitorDropWidget(MockMonitor("M2"), "2")
        
        col.add_monitor(w1)
        assert col.count() == 1
        
        col.insert_monitor(0, w2)
        assert col.count() == 2
        assert col.widget_at(0) == w2
        assert col.widget_at(1) == w1
        
        col.remove_monitor(w2)
        assert col.count() == 1
        assert col.widget_at(0) == w1

