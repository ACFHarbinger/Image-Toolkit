import math

from abc import ABCMeta, abstractmethod
from PySide6.QtCore import QObject, Qt, QPoint, QRect
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton

# --- SHARED LOGIC IMPLEMENTATIONS ---
# These functions will be injected into the classes by the Metaclass.


def _common_create_pagination_ui(self):
    """
    Creates the standardized pagination widget.
    Returns: (container_widget, controls_dict)
    controls_dict contains: 'combo', 'btn_prev', 'btn_page', 'btn_next'
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    lbl = QLabel(f"Images per page:")
    combo = QComboBox()
    combo.addItems(["20", "50", "100", "1000", "All"])
    combo.setCurrentText("100")

    btn_prev = QPushButton("< Prev")

    btn_page = QPushButton("Page 1 / 1")
    btn_page.setFixedWidth(120)

    btn_next = QPushButton("Next >")

    layout.addWidget(lbl)
    layout.addWidget(combo)
    layout.addStretch()
    layout.addWidget(btn_prev)
    layout.addWidget(btn_page)
    layout.addWidget(btn_next)

    controls = {
        "combo": combo,
        "btn_prev": btn_prev,
        "btn_page": btn_page,
        "btn_next": btn_next,
    }
    return container, controls


def _common_update_pagination_state(
    self, total_items, page_size, current_page, controls_dict
):
    """
    Updates the enabled state and text of pagination controls.
    """
    btn_page = controls_dict["btn_page"]
    btn_prev = controls_dict["btn_prev"]
    btn_next = controls_dict["btn_next"]

    if total_items == 0:
        btn_page.setText("Page 0 / 0")
        btn_page.setEnabled(False)
        btn_prev.setEnabled(False)
        btn_next.setEnabled(False)
        return 0, 0  # corrected_page, total_pages

    total_pages = math.ceil(total_items / page_size)

    # Ensure current page is valid
    if current_page >= total_pages:
        current_page = max(0, total_pages - 1)

    btn_page.setText(f"Page {current_page + 1} / {total_pages}")
    btn_page.setEnabled(True)
    btn_prev.setEnabled(current_page > 0)
    btn_next.setEnabled(current_page < total_pages - 1)

    return current_page, total_pages


def _common_calculate_columns(self, scroll_area, approx_width):
    """Calculates how many columns fit in the scroll area."""
    if not scroll_area:
        return 1

    viewport = scroll_area.viewport()
    width = viewport.width()
    if width <= 0:
        width = scroll_area.width()
    if width <= 0:
        # Fallback if widget isn't visible yet
        return 4

    return max(1, width // approx_width)


def _common_reflow_layout(self, layout, columns):
    """Re-organizes the grid layout to the new column count."""
    if not layout:
        return

    items = []
    placeholder = None

    # Extract items
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            if isinstance(widget, QLabel) and getattr(widget, "is_placeholder", False):
                placeholder = widget
            else:
                items.append(widget)

    # Re-add items
    if placeholder:
        layout.addWidget(placeholder, 0, 0, 1, columns, Qt.AlignCenter)
    else:
        for i, widget in enumerate(items):
            row = i // columns
            col = i % columns
            layout.addWidget(widget, row, col, Qt.AlignLeft | Qt.AlignTop)


def _common_is_visible(self, widget, viewport, visible_rect):
    """Checks if a widget intersects with the visible viewport area."""
    if not widget.isVisible():
        return False

    # Map widget position to viewport coordinates
    p = widget.mapTo(viewport, QPoint(0, 0))
    widget_rect = QRect(p, widget.size())

    return visible_rect.intersects(widget_rect)


def _common_get_paginated_slice(self, full_list, page, page_size):
    """Returns the subset of the list for the current page."""
    start = page * page_size
    end = start + page_size
    return full_list[start:end]


def _common_show_placeholder(self, layout, text, columns=1):
    """Clears layout and shows a placeholder label."""
    if not layout:
        return

    # Clear existing
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()

    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("color: #b9bbbe; padding: 20px; font-style: italic;")
    lbl.is_placeholder = True

    layout.addWidget(lbl, 0, 0, 1, columns, Qt.AlignCenter)


class MetaAbstractClassGallery(ABCMeta, type(QObject)):
    """
    A metaclass combining ABCMeta and Qt's metaclass.
    Acts as a Mixin Injector: It automatically adds common logic helper methods
    to any class that uses it, avoiding code duplication in the subclasses.
    """

    def __new__(mcs, name, bases, dct):
        # Inject shared logic into the class dictionary if not already present
        # This allows the subclasses to call self.common_method()

        injectables = {
            "common_create_pagination_ui": _common_create_pagination_ui,
            "common_update_pagination_state": _common_update_pagination_state,
            "common_calculate_columns": _common_calculate_columns,
            "common_reflow_layout": _common_reflow_layout,
            "common_is_visible": _common_is_visible,
            "common_get_paginated_slice": _common_get_paginated_slice,
            "common_show_placeholder": _common_show_placeholder,
        }

        for method_name, func in injectables.items():
            if method_name not in dct:
                dct[method_name] = func

        return super().__new__(mcs, name, bases, dct)

    @abstractmethod
    def get_default_config(self) -> dict:
        """Get default configuration."""
        pass

    @abstractmethod
    def set_config(self, config: dict):
        """Set input field values from selected configuration."""
        pass

    @staticmethod
    def join_list_str(text):
        """Convert a comma/space separated string to list of strings, stripping whitespace."""
        return [
            item.strip().lstrip(".")
            for item in text.replace(",", " ").split()
            if item.strip()
        ]
