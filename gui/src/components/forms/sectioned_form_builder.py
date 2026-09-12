"""Sectioned form builder for standardized, modular Qt forms (§5 R2.f, #567).

Provides FormSection and SectionedFormBuilder to eliminate repetitive boilerplate
across configuration tabs: scrollable container setup, group box sections, labeled rows,
path picker layouts, optional fields, and action rows.
"""

from __future__ import annotations

from typing import Callable, Literal, Sequence

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...styles import apply_shadow_effect
from ..elements.optional_field import OptionalField


class FormSection:
    """A titled QGroupBox section containing a layout (QFormLayout by default)."""

    def __init__(
        self,
        title: str,
        *,
        layout_type: Literal["form", "vertical", "horizontal"] = "form",
        parent: QWidget | None = None,
    ) -> None:
        self.group_box = QGroupBox(title, parent)
        self.layout_type = layout_type
        if layout_type == "form":
            self.layout: QLayout = QFormLayout(self.group_box)
        elif layout_type == "vertical":
            self.layout = QVBoxLayout(self.group_box)
        elif layout_type == "horizontal":
            self.layout = QHBoxLayout(self.group_box)
        else:
            raise ValueError(f"Unsupported layout_type: {layout_type}")

    @property
    def title(self) -> str:
        return self.group_box.title()

    @title.setter
    def title(self, text: str) -> None:
        self.group_box.setTitle(text)

    def add_row(
        self,
        label: str | QWidget | None,
        field: QWidget | QLayout | None = None,
    ) -> None:
        """Add a row to the section layout."""
        if isinstance(self.layout, QFormLayout):
            if label is not None and field is not None:
                self.layout.addRow(label, field)  # type: ignore[arg-type]
            elif label is not None and field is None:
                if isinstance(label, QWidget):
                    self.layout.addRow(label)
                else:
                    self.layout.addRow(QLabel(label))
            elif label is None and field is not None:
                if isinstance(field, QWidget):
                    self.layout.addRow(field)
                else:
                    self.layout.addRow(field)
        elif isinstance(self.layout, (QVBoxLayout, QHBoxLayout)):
            if label is not None and field is not None:
                row_layout = QHBoxLayout()
                lbl_widget = label if isinstance(label, QWidget) else QLabel(label)
                row_layout.addWidget(lbl_widget)
                if isinstance(field, QWidget):
                    row_layout.addWidget(field)
                elif isinstance(field, QLayout):
                    row_layout.addLayout(field)
                self.layout.addLayout(row_layout)
            elif label is not None and field is None:
                widget = label if isinstance(label, QWidget) else QLabel(label)
                self.layout.addWidget(widget)
            elif label is None and field is not None:
                if isinstance(field, QWidget):
                    self.layout.addWidget(field)
                elif isinstance(field, QLayout):
                    self.layout.addLayout(field)

    def add_widget(self, widget: QWidget) -> None:
        """Add a standalone widget spanning the row or column."""
        if isinstance(self.layout, QFormLayout):
            self.layout.addRow(widget)
        else:
            self.layout.addWidget(widget)

    def add_layout(self, layout: QLayout) -> None:
        """Add a sub-layout spanning the row or column."""
        if isinstance(self.layout, QFormLayout):
            self.layout.addRow(layout)
        else:
            self.layout.addLayout(layout)

    def add_path_picker(
        self,
        line_edit: QLineEdit,
        browse_btn: QPushButton,
        *,
        label: str | None = None,
        recent_btn: QToolButton | None = None,
        apply_shadow: bool = True,
    ) -> QHBoxLayout:
        """Add a standard path picker row [QLineEdit] [Browse...] [RecentBtn]."""
        row_layout = QHBoxLayout()
        row_layout.addWidget(line_edit)
        if apply_shadow:
            apply_shadow_effect(browse_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        row_layout.addWidget(browse_btn)
        if recent_btn is not None:
            row_layout.addWidget(recent_btn)

        if label is not None:
            self.add_row(label, row_layout)
        else:
            self.add_layout(row_layout)
        return row_layout

    def add_checkbox(
        self,
        text: str,
        *,
        checked: bool = False,
        on_toggled: Callable[[bool], None] | None = None,
        tooltip: str = "",
    ) -> QCheckBox:
        """Create and add a checkbox to the section."""
        cb = QCheckBox(text)
        cb.setChecked(checked)
        if tooltip:
            cb.setToolTip(tooltip)
        if on_toggled is not None:
            cb.toggled.connect(on_toggled)
        self.add_widget(cb)
        return cb

    def add_combo(
        self,
        label: str | None,
        items: Sequence[str],
        *,
        current: str | None = None,
        on_change: Callable[[str], None] | None = None,
        tooltip: str = "",
    ) -> QComboBox:
        """Create and add a combobox row to the section."""
        combo = QComboBox()
        combo.addItems(list(items))
        if current is not None:
            combo.setCurrentText(current)
        if tooltip:
            combo.setToolTip(tooltip)
        if on_change is not None:
            combo.currentTextChanged.connect(on_change)
        if label:
            self.add_row(label, combo)
        else:
            self.add_widget(combo)
        return combo

    def add_optional_field(
        self,
        title: str,
        inner_widget: QWidget,
        *,
        start_open: bool = False,
    ) -> OptionalField:
        """Create and add a collapsible OptionalField to the section."""
        field = OptionalField(title, inner_widget, start_open=start_open)
        self.add_widget(field)
        return field

    def add_stretch(self, stretch: int = 1) -> None:
        """Add stretch if layout is vertical or horizontal."""
        if isinstance(self.layout, (QVBoxLayout, QHBoxLayout)):
            self.layout.addStretch(stretch)


class SectionedFormBuilder:
    """Builder for sectioned groupbox and form layouts with scroll areas (§5 R2.f, #567)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        scrollable: bool = True,
        spacing: int = 10,
        margins: tuple[int, int, int, int] = (0, 0, 0, 0),
    ) -> None:
        self.parent = parent
        self.scrollable = scrollable
        self.sections: list[FormSection] = []

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(*margins)
        self.content_layout.setSpacing(spacing)

        if scrollable:
            self.scroll_area: QScrollArea | None = QScrollArea(parent)
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setStyleSheet("QScrollArea { border: none; }")
            self.scroll_area.setWidget(self.content_widget)
            self.root_widget: QWidget = self.scroll_area
        else:
            self.scroll_area = None
            self.root_widget = self.content_widget

    def add_section(
        self,
        title: str,
        *,
        layout_type: Literal["form", "vertical", "horizontal"] = "form",
    ) -> FormSection:
        """Create and add a titled FormSection (QGroupBox)."""
        section = FormSection(title, layout_type=layout_type, parent=self.content_widget)
        self.sections.append(section)
        self.content_layout.addWidget(section.group_box)
        return section

    def add_widget(self, widget: QWidget) -> None:
        """Add a standalone widget to the main content layout."""
        self.content_layout.addWidget(widget)

    def add_layout(self, layout: QLayout) -> None:
        """Add a sub-layout to the main content layout."""
        self.content_layout.addLayout(layout)

    def add_action_row(
        self,
        *widgets: QWidget,
        stretch_before: bool = False,
        stretch_after: bool = False,
    ) -> QHBoxLayout:
        """Add a horizontal row of action widgets (e.g. buttons/status)."""
        row = QHBoxLayout()
        if stretch_before:
            row.addStretch()
        for w in widgets:
            row.addWidget(w)
        if stretch_after:
            row.addStretch()
        self.content_layout.addLayout(row)
        return row

    def add_stretch(self, stretch: int = 1) -> None:
        """Add stretch to the main content layout."""
        self.content_layout.addStretch(stretch)

    def build(self, target_layout: QLayout | None = None) -> QWidget:
        """Mount root_widget into target_layout if supplied, and return root_widget."""
        if target_layout is not None:
            target_layout.addWidget(self.root_widget)
        return self.root_widget


__all__ = ["FormSection", "SectionedFormBuilder"]
