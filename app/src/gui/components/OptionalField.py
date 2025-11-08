from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from ..styles import apply_shadow_effect


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
        self.toggle_btn.setObjectName("OptionalFieldToggleBtn") # Keep the object name
        self.toggle_btn.setFixedWidth(30)
        self.toggle_btn.setFlat(True)
        apply_shadow_effect(self.toggle_btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

        self.label = QLabel(title)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(6, 3, 6, 3)
        header_layout.addWidget(self.toggle_btn)
        header_layout.addWidget(self.label)
        header_layout.addStretch(1)

        header_frame = QFrame()
        header_frame.setLayout(header_layout)
        header_frame.setFrameShape(QFrame.Box)

        # Adaptive color based on theme
        palette = QApplication.palette()
        base_color = palette.color(QPalette.Base)
        text_color = palette.color(QPalette.Text)
        border_color = palette.color(QPalette.Mid)
        hover_color = base_color.lighter(110) if base_color.value() < 128 else base_color.darker(110)
        
        # Use the name strings for CSS
        text_color_name = text_color.name()

        # Apply the style to the QFrame
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {base_color.name()};
                border: 1px solid {border_color.name()};
                border-radius: 3px;
            }}
            QLabel {{
                color: {text_color_name};
                font-weight: 600;
            }}
            /* Target the button using the ID and set color and background to transparent */
            QPushButton#OptionalFieldToggleBtn {{ 
                color: {text_color_name}; /* Forcing the foreground color */
                background-color: transparent; 
                border: none;
                padding: 0; /* Minimize padding influence */
                font-size: 14px;
            }}
            /* Add hover effect to the button itself for debugging/visual confirmation */
            QPushButton#OptionalFieldToggleBtn:hover {{
                color: {hover_color.name()}; /* Ensure color changes on hover */
                background-color: transparent;
            }}
            QFrame:hover {{
                background-color: {hover_color.name()};
            }}
        """)

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