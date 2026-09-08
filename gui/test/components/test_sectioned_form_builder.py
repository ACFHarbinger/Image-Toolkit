"""Unit tests for SectionedFormBuilder and FormSection (§5 R2.f, #567)."""

from __future__ import annotations

import pytest
from gui.src.components.forms import FormSection, SectionedFormBuilder
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


@pytest.mark.gui
def test_form_section_creation(q_app) -> None:
    widget = QWidget()
    section = FormSection("Test Section", layout_type="form", parent=widget)

    assert section.title == "Test Section"
    assert isinstance(section.layout, QFormLayout)

    section.title = "Updated Title"
    assert section.title == "Updated Title"


@pytest.mark.gui
def test_form_section_add_row(q_app) -> None:
    widget = QWidget()
    section = FormSection("Settings", layout_type="form", parent=widget)

    edit = QLineEdit()
    section.add_row("Name:", edit)
    assert section.layout.rowCount() == 1

    label_widget = QLabel("Custom Label:")
    edit2 = QLineEdit()
    section.add_row(label_widget, edit2)
    assert section.layout.rowCount() == 2

    span_edit = QLineEdit()
    section.add_row(span_edit)
    assert section.layout.rowCount() == 3


@pytest.mark.gui
def test_form_section_path_picker(q_app) -> None:
    widget = QWidget()
    section = FormSection("Paths", layout_type="form", parent=widget)

    line_edit = QLineEdit()
    browse_btn = QPushButton("Browse...")
    recent_btn = QToolButton()

    row = section.add_path_picker(
        line_edit,
        browse_btn,
        label="Input Path:",
        recent_btn=recent_btn,
    )
    assert isinstance(row, QHBoxLayout)
    assert row.count() == 3
    assert section.layout.rowCount() == 1


@pytest.mark.gui
def test_form_section_helpers(q_app) -> None:
    widget = QWidget()
    section = FormSection("Helpers", layout_type="form", parent=widget)

    toggled = []
    cb = section.add_checkbox(
        "Enable feature",
        checked=False,
        on_toggled=lambda val: toggled.append(val),
        tooltip="Test tooltip",
    )
    assert not cb.isChecked()
    assert cb.toolTip() == "Test tooltip"
    cb.setChecked(True)
    assert toggled == [True]

    changed = []
    combo = section.add_combo(
        "Options:",
        ["Option A", "Option B", "Option C"],
        current="Option B",
        on_change=lambda val: changed.append(val),
    )
    assert combo.currentText() == "Option B"
    combo.setCurrentText("Option C")
    assert changed == ["Option C"]

    inner = QWidget()
    field = section.add_optional_field("Advanced", inner, start_open=False)
    assert not field.inner_widget.isVisible()


@pytest.mark.gui
def test_sectioned_form_builder_scrollable(q_app) -> None:
    parent = QWidget()
    builder = SectionedFormBuilder(parent, scrollable=True)

    assert isinstance(builder.root_widget, QScrollArea)
    assert builder.scroll_area is builder.root_widget
    assert builder.scroll_area.widgetResizable()

    sec1 = builder.add_section("Section 1")
    sec2 = builder.add_section("Section 2")
    assert len(builder.sections) == 2
    assert sec1.title == "Section 1"
    assert sec2.title == "Section 2"

    action_row = builder.add_action_row(QPushButton("Save"), QPushButton("Cancel"), stretch_before=True)
    assert isinstance(action_row, QHBoxLayout)

    target_layout = QVBoxLayout(parent)
    built_widget = builder.build(target_layout)
    assert built_widget is builder.root_widget
    assert target_layout.count() == 1


@pytest.mark.gui
def test_sectioned_form_builder_non_scrollable(q_app) -> None:
    parent = QWidget()
    builder = SectionedFormBuilder(parent, scrollable=False)

    assert builder.scroll_area is None
    assert builder.root_widget is builder.content_widget

    builder.add_section("General")
    assert len(builder.sections) == 1
