import math

from abc import ABCMeta, abstractmethod
from PySide6.QtCore import QObject, Qt, QPoint, QRect
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QLineEdit,
    QSlider,
    QFrame,
)

# --- SHARED LOGIC IMPLEMENTATIONS ---
# These functions will be injected into the classes by the Metaclass.


def _make_vline():
    """Thin vertical separator widget for pagination bars."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    line.setFixedWidth(2)
    return line


def _common_create_pagination_ui(self):
    """
    Creates the standardized pagination widget (§3.9 + §4.11).

    Returns: (container_widget, controls_dict)
    controls_dict keys:
        'combo', 'btn_prev', 'btn_page', 'btn_next',
        'item_range_lbl',          # §3.9 — "Items A–B of C"
        'thumb_slider',            # §4.11 — thumbnail size slider (64–512 px)
        'thumb_size_lbl',          # §4.11 — e.g. "180 px"
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    lbl = QLabel("Images per page:")
    combo = QComboBox()
    combo.addItems(["20", "50", "100", "150", "250", "500", "1000", "All"])
    combo.setCurrentText("150")
    combo.setAccessibleName("Images per page")

    # §2.13A — sort controls
    sort_lbl = QLabel("Sort:")
    sort_combo = QComboBox()
    sort_combo.addItems(["Name", "Date Modified", "File Size", "Extension"])
    sort_combo.setFixedWidth(120)
    sort_combo.setAccessibleName("Sort by")
    sort_dir_btn = QPushButton("↑")
    sort_dir_btn.setFixedWidth(28)
    sort_dir_btn.setToolTip("Toggle sort direction")
    sort_dir_btn.setAccessibleName("Toggle sort direction")

    btn_prev = QPushButton("< Prev")
    btn_prev.setAccessibleName("Previous page")
    btn_page = QPushButton("Page 1 / 1")
    btn_page.setFixedWidth(120)
    btn_page.setAccessibleName("Current page")
    btn_next = QPushButton("Next >")
    btn_next.setAccessibleName("Next page")

    # §3.9 — item range indicator
    item_range_lbl = QLabel("0 images")
    item_range_lbl.setMinimumWidth(120)
    item_range_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    item_range_lbl.setAccessibleName("Item range")

    # §4.11 — thumbnail size slider
    thumb_slider = QSlider(Qt.Orientation.Horizontal)
    thumb_slider.setRange(64, 512)
    thumb_slider.setSingleStep(16)
    thumb_slider.setPageStep(32)
    thumb_slider.setValue(180)
    thumb_slider.setFixedWidth(110)
    thumb_slider.setToolTip("Thumbnail size (64–512 px)")
    thumb_slider.setAccessibleName("Thumbnail size")
    thumb_slider.setAccessibleDescription("Drag to resize gallery thumbnails between 64 and 512 pixels")

    thumb_size_lbl = QLabel("180 px")
    thumb_size_lbl.setMinimumWidth(44)
    thumb_size_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    layout.addWidget(lbl)
    layout.addWidget(combo)
    layout.addWidget(sort_lbl)
    layout.addWidget(sort_combo)
    layout.addWidget(sort_dir_btn)
    layout.addStretch()
    layout.addWidget(item_range_lbl)
    layout.addWidget(_make_vline())
    layout.addWidget(btn_prev)
    layout.addWidget(btn_page)
    layout.addWidget(btn_next)
    layout.addWidget(_make_vline())
    layout.addWidget(QLabel("⊞"))
    layout.addWidget(thumb_slider)
    layout.addWidget(thumb_size_lbl)

    controls = {
        "combo": combo,
        "btn_prev": btn_prev,
        "btn_page": btn_page,
        "btn_next": btn_next,
        "item_range_lbl": item_range_lbl,
        "thumb_slider": thumb_slider,
        "thumb_size_lbl": thumb_size_lbl,
        "sort_combo": sort_combo,        # §2.13A
        "sort_dir_btn": sort_dir_btn,    # §2.13A
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


def _common_create_search_input(self, placeholder_text='Search… (-exclude "exact" a|b)'):
    """
    Creates a standardized search input widget.
    Placeholder hints at the extended operators added in §2.13E.
    """
    search_input = QLineEdit()
    search_input.setPlaceholderText(placeholder_text)
    search_input.setStyleSheet(
        """
        QLineEdit {
            padding: 5px;
            border-radius: 4px;
            border: 1px solid #4f545c;
            background-color: #202225;
            color: white;
        }
        QLineEdit:focus {
            border: 1px solid #5865f2;
        }
        """
    )
    return search_input


def _common_filter_string_list(self, full_list, query):
    """Filter a list of strings with extended search operators (§2.13E).

    Supported syntax:
      -term        exclude paths containing "term"
      "phrase"     exact substring (case-insensitive)
      a|b          OR — matches paths containing "a" OR "b"
      plain text   standard case-insensitive substring match

    Tokens are AND-combined: all must match for a path to pass.
    """
    if not query:
        return full_list

    import re as _re

    tokens = []
    remaining = query.strip()
    # Extract quoted phrases first
    for phrase in _re.findall(r'"([^"]+)"', remaining):
        tokens.append(("phrase", phrase.lower()))
    remaining = _re.sub(r'"[^"]+"', "", remaining)
    # Remaining tokens split by whitespace
    for tok in remaining.split():
        if tok.startswith("-") and len(tok) > 1:
            tokens.append(("exclude", tok[1:].lower()))
        elif "|" in tok:
            tokens.append(("or", [p.lower() for p in tok.split("|") if p]))
        else:
            tokens.append(("include", tok.lower()))

    if not tokens:
        return full_list

    result = []
    for item in full_list:
        lower = item.lower()
        match = True
        for kind, val in tokens:
            if kind == "include":
                if val not in lower:
                    match = False
                    break
            elif kind == "exclude":
                if val in lower:
                    match = False
                    break
            elif kind == "phrase":
                if val not in lower:
                    match = False
                    break
            elif kind == "or":
                if not any(v in lower for v in val):
                    match = False
                    break
        if match:
            result.append(item)
    return result


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
            "common_create_search_input": _common_create_search_input,
            "common_filter_string_list": _common_filter_string_list,
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
