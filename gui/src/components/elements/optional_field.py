from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.src.theming.theme_api import color, qss

from ...styles import apply_shadow_effect


class OptionalField(QWidget):
    """
    A collapsible section for optional inputs.
    Displays a label with a +/- button, expands or collapses to show inner widget(s).
    """

    def __init__(self, title: str, inner_widget: QWidget, start_open: bool = False):
        super().__init__()

        self.inner_widget = inner_widget
        self.inner_widget.setVisible(start_open)

        # Header bar
        self.toggle_btn = QPushButton("➕" if not start_open else "➖")
        self.toggle_btn.setObjectName("OptionalFieldToggleBtn")  # Keep the object name
        self.toggle_btn.setFixedWidth(30)
        self.toggle_btn.setFlat(True)
        apply_shadow_effect(
            self.toggle_btn, color_hex=color("window_bg"), radius=8, x_offset=0, y_offset=3
        )

        self.label = QLabel(title)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(6, 3, 6, 3)
        header_layout.addWidget(self.toggle_btn)
        header_layout.addWidget(self.label)
        header_layout.addStretch(1)

        header_frame = QFrame()
        header_frame.setLayout(header_layout)
        header_frame.setFrameShape(QFrame.Shape.Box)

        # Adaptive color based on theme
        palette = QApplication.palette()
        base_color = palette.color(QPalette.ColorRole.Base)
        text_color = palette.color(QPalette.ColorRole.Text)
        border_color = palette.color(QPalette.ColorRole.Mid)
        hover_color = (
            base_color.lighter(110)
            if base_color.value() < 128
            else base_color.darker(110)
        )

        # Use the name strings for CSS
        text_color_name = text_color.name()

        # Apply the style to the QFrame
        header_frame.setStyleSheet(
            qss(
                "optional_field_header",
                BASE=base_color.name(),
                BORDER=border_color.name(),
                TEXT=text_color_name,
                HOVER=hover_color.name(),
            )
        )

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(header_frame)
        main_layout.addWidget(self.inner_widget)
        self.setLayout(main_layout)

        # Connect toggles
        self.toggle_btn.clicked.connect(self.toggle)
        header_frame.mousePressEvent = lambda e: self.toggle()

    def toggle(self):
        visible = not self.inner_widget.isVisible()
        self.inner_widget.setVisible(visible)
        self.toggle_btn.setText("➖" if visible else "➕")

    def set_open(self, open: bool):
        """
        Explicitly sets the expanded/collapsed state of the section.
        """
        # Only trigger the toggle if the current state differs from the requested state
        if self.inner_widget.isVisible() != open:
            self.toggle()
