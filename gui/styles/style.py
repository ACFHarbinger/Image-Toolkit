from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


def apply_shadow_effect(widget, color_hex="#000000", radius=10, x_offset=0, y_offset=4):
    """Creates and applies a QGraphicsDropShadowEffect to a given widget."""
    shadow = QGraphicsDropShadowEffect(widget)

    # 1. Set the color (black with transparency)
    shadow.setColor(QColor(color_hex))

    # 2. Set the blur radius (controls the softness/spread)
    shadow.setBlurRadius(radius)

    # 3. Set the offset (controls the shadow position, similar to CSS x/y)
    shadow.setOffset(x_offset, y_offset)

    # 4. Apply the effect to the widget
    widget.setGraphicsEffect(shadow)
    return shadow


# --- THEME DEFINITIONS ---
# Dark Theme Accent (Cyan/Teal)
DARK_ACCENT_COLOR = "#00bcd4"
DARK_ACCENT_HOVER = "#0097a7"
DARK_ACCENT_PRESSED = "#00838f"
DARK_ACCENT_MUTED = "#3e3e3e"

# Dark Theme Backgrounds/Text
DARK_BG = "#1e1e1e"
DARK_SECONDARY_BG = "#2d2d30"
DARK_TEXT = "#cccccc"
DARK_MUTED_TEXT = "#888888"
DARK_BORDER = "#3e3e3e"

# Light Theme Accent (Professional Blue)
LIGHT_ACCENT_COLOR = "#007AFF"
LIGHT_ACCENT_HOVER = "#0056b3"
LIGHT_ACCENT_PRESSED = "#004085"

# Light Theme Backgrounds/Text
LIGHT_BG = "#f5f5f5"
LIGHT_SECONDARY_BG = "#ffffff"
LIGHT_TEXT = "#1e1e1e"
LIGHT_MUTED_TEXT = "#555555"
LIGHT_BORDER = "#cccccc"


# --- DARK THEME QSS ---
DARK_QSS = f"""
    /* --- DARK THEME STYLE SHEET (Cyan Accent) --- */
    QWidget, QMainWindow, QDialog {{
        background-color: {DARK_BG};
        color: {DARK_TEXT};
        font-family: 'Segoe UI', 'Arial', sans-serif;
        font-size: 10pt;
    }}

    /* --- Buttons --- */
    QPushButton {{
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {DARK_ACCENT_COLOR}, stop: 1 {DARK_ACCENT_HOVER});
        color: white;
        border: none;
        padding: 10px 18px;
        border-radius: 6px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {DARK_ACCENT_COLOR};
    }}
    QPushButton:pressed {{
        background: {DARK_ACCENT_PRESSED};
        padding-top: 12px;
        padding-bottom: 8px;
    }}
    QPushButton:disabled {{
        background-color: {DARK_ACCENT_MUTED};
        color: {DARK_MUTED_TEXT};
    }}

    /* --- Tab Widget Styling --- */
    QTabWidget::pane {{
        border: 1px solid {DARK_BORDER};
        background-color: {DARK_BG};
        border-radius: 8px;
    }}
    QTabBar::tab {{
        background: {DARK_SECONDARY_BG};
        color: #aaaaaa;
        padding: 10px 20px;
        border: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background: {DARK_BG};
        color: {DARK_ACCENT_COLOR};
        border-bottom: 2px solid {DARK_ACCENT_COLOR};
        font-weight: bold;
    }}
    QTabBar::tab:hover:!selected {{
        background: {DARK_BORDER};
        color: {DARK_TEXT};
    }}

    /* --- Input Fields --- */
    QLineEdit, QComboBox, QSpinBox, QTextEdit {{
        background-color: {DARK_SECONDARY_BG};
        color: {DARK_TEXT};
        border: 1px solid {DARK_BORDER};
        padding: 8px;
        border-radius: 4px;
        selection-background-color: {DARK_ACCENT_COLOR};
        selection-color: white;
    }}

    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{
        border: 1px solid {DARK_ACCENT_COLOR};
        background-color: #363639;
    }}

    /* --- Group Boxes --- */
    QGroupBox {{
        border: 1px solid {DARK_BORDER};
        margin-top: 25px;
        border-radius: 8px;
        padding-top: 15px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top center;
        padding: 0 12px;
        background-color: {DARK_ACCENT_COLOR};
        color: white;
        font-size: 11pt;
        border-radius: 4px;
    }}

    /* --- Labels --- */
    QLabel {{
        color: {DARK_TEXT};
        background-color: transparent;
    }}

    /* --- Header Widget Fix --- */
    QWidget#header_widget {{
        background-color: {DARK_SECONDARY_BG};
        border-bottom: 2px solid {DARK_ACCENT_COLOR};
    }}

    /* --- NEW: Scroll Bar Styling for visibility --- */
    QScrollBar:vertical, QScrollBar:horizontal {{
        border: none;
        background: {DARK_SECONDARY_BG}; /* Dark background groove */
        width: 12px;
        height: 12px;
    }}

    QScrollBar::handle:vertical {{
        background: {DARK_ACCENT_COLOR}; /* Bright cyan handle */
        min-height: 20px;
        border-radius: 6px;
        margin: 2px 2px 2px 2px;
    }}

    QScrollBar::handle:horizontal {{
        background: {DARK_ACCENT_COLOR}; /* Bright cyan handle */
        min-width: 20px;
        border-radius: 6px;
        margin: 2px 2px 2px 2px;
    }}

    QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
        background: {DARK_ACCENT_HOVER};
    }}

    /* Remove default arrows */
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        border: none;
        background: none;
    }}
"""


# --- LIGHT THEME QSS ---
LIGHT_QSS = f"""
    /* --- LIGHT THEME STYLE SHEET (Blue Accent) --- */
    QWidget, QMainWindow, QDialog {{
        background-color: {LIGHT_BG};
        color: {LIGHT_TEXT};
        font-family: 'Segoe UI', 'Arial', sans-serif;
        font-size: 10pt;
    }}

    /* --- Buttons --- */
    QPushButton {{
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {LIGHT_ACCENT_COLOR}, stop: 1 {LIGHT_ACCENT_HOVER});
        color: white;
        border: 1px solid {LIGHT_ACCENT_HOVER};
        padding: 10px 18px;
        border-radius: 6px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {LIGHT_ACCENT_COLOR};
    }}
    QPushButton:pressed {{
        background: {LIGHT_ACCENT_PRESSED};
        padding-top: 12px;
        padding-bottom: 8px;
    }}
    QPushButton:disabled {{
        background-color: {LIGHT_BORDER};
        color: {LIGHT_MUTED_TEXT};
        border-color: {LIGHT_BORDER};
    }}

    /* --- Tab Widget Styling --- */
    QTabWidget::pane {{
        border: 1px solid {LIGHT_BORDER};
        background-color: {LIGHT_BG};
        border-radius: 8px;
    }}
    QTabBar::tab {{
        background: {LIGHT_SECONDARY_BG};
        color: {LIGHT_TEXT};
        padding: 10px 20px;
        border: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background: {LIGHT_BG};
        color: {LIGHT_ACCENT_COLOR};
        border-bottom: 2px solid {LIGHT_ACCENT_COLOR};
        font-weight: bold;
    }}
    QTabBar::tab:hover:!selected {{
        background: {LIGHT_BORDER};
        color: {LIGHT_TEXT};
    }}

    /* --- Input Fields --- */
    QLineEdit, QComboBox, QSpinBox, QTextEdit {{
        background-color: {LIGHT_SECONDARY_BG};
        color: {LIGHT_TEXT};
        border: 1px solid {LIGHT_BORDER};
        padding: 8px;
        border-radius: 4px;
        selection-background-color: {LIGHT_ACCENT_COLOR};
        selection-color: white;
    }}

    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{
        border: 1px solid {LIGHT_ACCENT_COLOR};
        background-color: {LIGHT_SECONDARY_BG};
    }}

    /* --- Group Boxes --- */
    QGroupBox {{
        border: 1px solid {LIGHT_BORDER};
        margin-top: 25px;
        border-radius: 8px;
        padding-top: 15px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top center;
        padding: 0 12px;
        background-color: {LIGHT_ACCENT_COLOR};
        color: white;
        font-size: 11pt;
        border-radius: 4px;
    }}

    /* --- Labels --- */
    QLabel {{
        color: {LIGHT_TEXT};
        background-color: transparent;
    }}

    /* --- Header Widget Fix --- */
    QWidget#header_widget {{
        background-color: {DARK_SECONDARY_BG}; /* Keep dark header for contrast */
        border-bottom: 2px solid {LIGHT_ACCENT_COLOR}; /* Use light theme accent color for border */
    }}

    /* --- NEW: Scroll Bar Styling for professional blue --- */
    QScrollBar:vertical, QScrollBar:horizontal {{
        border: none;
        background: {LIGHT_SECONDARY_BG}; /* Light background groove */
        width: 12px;
        height: 12px;
    }}

    QScrollBar::handle:vertical {{
        background: {LIGHT_ACCENT_COLOR}; /* Professional blue handle */
        min-height: 20px;
        border-radius: 6px;
        margin: 2px 2px 2px 2px;
    }}

    QScrollBar::handle:horizontal {{
        background: {LIGHT_ACCENT_COLOR}; /* Professional blue handle */
        min-width: 20px;
        border-radius: 6px;
        margin: 2px 2px 2px 2px;
    }}

    QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
        background: {LIGHT_ACCENT_HOVER};
    }}

    /* Remove default arrows */
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        border: none;
        background: none;
    }}
"""

# Default export (for backward compatibility)
GLOBAL_QSS = DARK_QSS

# Define primary button styles
STYLE_SYNC_RUN = """
    QPushButton { background:#2ecc71; color:white; padding:12px 16px;
                    font-size:14pt; border-radius:8px; font-weight:bold; }
    QPushButton:hover { background:#1e8449; }
    QPushButton:disabled { background:#4f545c; color:#a0a0a0; }
"""
STYLE_SYNC_STOP = """
    QPushButton { background:#e74c3c; color:white; padding:12px 16px;
                    font-size:14pt; border-radius:8px; font-weight:bold; }
    QPushButton:hover { background:#c0392b; }
    QPushButton:disabled { background:#4f545c; color:#a0a0a0; }
"""

# Define shared button styles for the Start/Cancel button
STYLE_SCAN_START = """
    QPushButton { background-color: #e67e22; color: white; font-weight: bold; padding: 8px; }
    QPushButton:hover { background-color: #d35400; }
"""

STYLE_SCAN_CANCEL = """
    QPushButton { background-color: #c0392b; color: white; font-weight: bold; padding: 8px; }
    QPushButton:hover { background-color: #a93226; }
"""

SHARED_BUTTON_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #667eea, stop:1 #764ba2);
        color: white; font-weight: bold; font-size: 14px;
        padding: 14px 8px; border-radius: 10px; min-height: 44px;
    }
    QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #764ba2, stop:1 #667eea); }
    QPushButton:disabled { background: #718096; }
    QPushButton:pressed { background: #5a67d8; }
"""

# --- Consistent Main Action Button Styles ---

STYLE_START_ACTION = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #667eea, stop:1 #764ba2);
        color: white; font-weight: bold; font-size: 14px;
        padding: 14px 8px; border-radius: 10px; min-height: 44px;
    }
    QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #764ba2, stop:1 #667eea); }
    QPushButton:disabled { background: #718096; }
    QPushButton:pressed { background: #5a67d8; }
"""

STYLE_STOP_ACTION = """
    QPushButton {
        background-color: #cc3333; color: white; font-weight: bold; font-size: 14px;
        padding: 14px 8px; border-radius: 10px; min-height: 44px;
    }
    QPushButton:hover { background-color: #ff4444; }
    QPushButton:disabled { background: #718096; }
    QPushButton:pressed { background-color: #992222; }
"""
# -------------------------------------------
