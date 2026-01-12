from gui.src.components.draggable_monitor_container import (
    DraggableMonitorContainer,
    MonitorColumn,
)
from gui.src.components.monitor_drop_widget import MonitorDropWidget


class MockMonitor:
    def __init__(self, name="TestMonitor", id="1"):
        self.name = name
        self.id = id


class TestMonitorColumnLogic:
    def test_default_structure(self, q_app):
        container = DraggableMonitorContainer()
        assert container.layout_vbox.count() == 1  # Initial empty row

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

    def test_layout_structure_serialization(self, q_app):
        container = DraggableMonitorContainer()
        # qtbot.addWidget(container) -> not needed if using q_app, or use container.show()
        container.show()

        # Create dummy widgets with monitor IDs
        # MonitorDropWidget(monitor, monitor_id)
        w1 = MonitorDropWidget(MockMonitor("M1"), "M1")
        w2 = MonitorDropWidget(MockMonitor("M2"), "M2")
        w3 = MonitorDropWidget(MockMonitor("M3"), "M3")
        w4 = MonitorDropWidget(MockMonitor("M4"), "M4")

        # Setup: Row 1: [M1, M2] | [M3]
        #        Row 2: [M4]

        # Creating logic manually to simulate structure
        # Row 1
        r1 = container.layout_vbox.itemAt(0).widget()  # Default first row

        col1 = MonitorColumn()
        col1.add_monitor(w1)
        col1.add_monitor(w2)
        r1.layout().addWidget(col1)

        col2 = MonitorColumn()
        col2.add_monitor(w3)
        r1.layout().addWidget(col2)

        # Row 2
        r2 = container._add_new_row()
        col3 = MonitorColumn()
        col3.add_monitor(w4)
        r2.layout().addWidget(col3)

        # Test GET
        structure = container.get_layout_structure()
        expected = [[["M1", "M2"], ["M3"]], [["M4"]]]
        assert structure == expected

        # Test SET
        # Clear and restore in different order using SET
        widgets_map = {"M1": w1, "M2": w2, "M3": w3, "M4": w4}
        new_structure = [
            [["M4", "M1"]],  # Row 1: Col 1 has M4, M1
            [["M2"], ["M3"]],  # Row 2: Col 1 has M2, Col 2 has M3
        ]

        container.set_layout_structure(new_structure, widgets_map)

        # Verify structure
        restored = container.get_layout_structure()
        assert restored == new_structure

        # Verify orphaned monitors handling
        # Config has only M1. M2, M3, M4 are orphans.
        partial_structure = [[["M1"]]]
        container.set_layout_structure(partial_structure, widgets_map)

        final_struct = container.get_layout_structure()
        # Expect: Row 1: [[M1]]
        #         Row 2: [[M2], [M3], [M4]]  (Default orphan handling puts them in new row, usually 1 col per widget?)
        # Let's check logic: "orphans ... orphans.append(widget) ... create new row ... for widget: new_col ... addWidget(new_col)"
        # So yes, each in own column in a new row.

        assert len(final_struct) == 2
        assert final_struct[0] == [["M1"]]
        # Orphans row might be order-dependent on dict iteration, so just check membership
        orphan_row = final_struct[1]
        assert len(orphan_row) == 3  # 3 columns
        # Check contents flattened
        flattened_orphans = [item for sublist in orphan_row for item in sublist]
        assert set(flattened_orphans) == {"M2", "M3", "M4"}

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
