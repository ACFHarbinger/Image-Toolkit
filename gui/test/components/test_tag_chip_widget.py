"""Unit tests for TagChipWidget and TagChipGroup components (§2.22 Option A)."""

import pytest
from gui.src.components.tag_chip_widget import FlowLayout, TagChipGroup, TagChipWidget
from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QLabel, QPushButton, QWidget


@pytest.mark.gui
def test_tag_chip_widget_toggle(q_app):
    chip = TagChipWidget("landscape", active=False)

    assert not chip.is_active()

    chip.set_active(True)
    assert chip.is_active()


@pytest.mark.gui
def test_tag_chip_group_selection(q_app):
    group = TagChipGroup()

    tags = ["cat", "dog", "bird"]
    group.set_tags(tags, selected=["cat"])

    assert group.get_selected_tags() == ["cat"]

    # Toggle dog chip
    group._chips[1].set_active(True)
    assert sorted(group.get_selected_tags()) == ["cat", "dog"]

    # Remove bird chip
    group.remove_tag("bird")
    assert [c.tag_text for c in group._chips] == ["cat", "dog"]


@pytest.mark.gui
def test_flow_layout_add_stretch_right_anchors(q_app):
    host = QWidget()
    layout = FlowLayout(host, spacing=6)
    left = QLabel("Interval")
    left.setFixedSize(QSize(80, 24))
    right = QPushButton("Set")
    right.setFixedSize(QSize(60, 36))
    layout.addWidget(left)
    layout.addStretch(1)
    layout.addWidget(right)
    host.show()
    layout._do_layout(QRect(0, 0, 400, 80), test_only=False)

    assert right.x() > left.x() + left.width()
    leftover_gap = right.x() - (left.x() + left.width())
    assert leftover_gap > 50
    left_mid = left.y() + left.height() / 2
    right_mid = right.y() + right.height() / 2
    assert abs(left_mid - right_mid) <= 1


@pytest.mark.gui
def test_flow_layout_still_wraps_at_narrow_width(q_app):
    host = QWidget()
    layout = FlowLayout(host, spacing=6)
    a = QPushButton("AAAA")
    a.setFixedSize(QSize(70, 24))
    b = QPushButton("BBBB")
    b.setFixedSize(QSize(70, 24))
    layout.addWidget(a)
    layout.addStretch(1)
    layout.addWidget(b)
    host.show()
    layout._do_layout(QRect(0, 0, 100, 200), test_only=False)

    assert b.y() > a.y()

