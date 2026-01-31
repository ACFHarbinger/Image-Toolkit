import os
import re

from string import Template
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


def parse_theme_vars():
    """Parses variables from theme.qss file."""
    path = os.path.join(os.path.dirname(__file__), "qss", "theme.qss")
    vars_dict = {}
    try:
        with open(path, "r") as f:
            content = f.read()
            # Find the @vars ... @end block
            match = re.search(r"@vars\n(.*?)\n@end", content, re.DOTALL)
            if match:
                vars_block = match.group(1)
                for line in vars_block.splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        vars_dict[key.strip()] = value.strip().rstrip(";")
    except FileNotFoundError:
        print(f"Warning: Theme QSS file not found: {path}")
    return vars_dict


# Load theme variables globally
THEME_VARS = parse_theme_vars()


def load_qss(filename):
    """Loads QSS content from a file and performs variable substitution."""
    path = os.path.join(os.path.dirname(__file__), "qss", filename)
    try:
        with open(path, "r") as f:
            content = f.read()
            # Perform variable substitution
            return Template(content).safe_substitute(THEME_VARS)
    except FileNotFoundError:
        print(f"Warning: QSS file not found: {path}")
        return ""


def apply_shadow_effect(widget, color_hex="#000000", radius=10, x_offset=0, y_offset=4):
    """Creates and applies a QGraphicsDropShadowEffect to a given widget."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setColor(QColor(color_hex))
    shadow.setBlurRadius(radius)
    shadow.setOffset(x_offset, y_offset)
    widget.setGraphicsEffect(shadow)
    return shadow


# --- THEME DEFINITIONS (Populated from theme.qss) ---
DARK_ACCENT_COLOR = THEME_VARS.get("DARK_ACCENT_COLOR", "#00bcd4")
DARK_ACCENT_HOVER = THEME_VARS.get("DARK_ACCENT_HOVER", "#0097a7")
DARK_ACCENT_PRESSED = THEME_VARS.get("DARK_ACCENT_PRESSED", "#00838f")
DARK_ACCENT_MUTED = THEME_VARS.get("DARK_ACCENT_MUTED", "#3e3e3e")

DARK_BG = THEME_VARS.get("DARK_BG", "#1e1e1e")
DARK_SECONDARY_BG = THEME_VARS.get("DARK_SECONDARY_BG", "#2d2d30")
DARK_TEXT = THEME_VARS.get("DARK_TEXT", "#cccccc")
DARK_MUTED_TEXT = THEME_VARS.get("DARK_MUTED_TEXT", "#888888")
DARK_BORDER = THEME_VARS.get("DARK_BORDER", "#3e3e3e")

LIGHT_ACCENT_COLOR = THEME_VARS.get("LIGHT_ACCENT_COLOR", "#007AFF")
LIGHT_ACCENT_HOVER = THEME_VARS.get("LIGHT_ACCENT_HOVER", "#0056b3")
LIGHT_ACCENT_PRESSED = THEME_VARS.get("LIGHT_ACCENT_PRESSED", "#004085")

LIGHT_BG = THEME_VARS.get("LIGHT_BG", "#f5f5f5")
LIGHT_SECONDARY_BG = THEME_VARS.get("LIGHT_SECONDARY_BG", "#ffffff")
LIGHT_TEXT = THEME_VARS.get("LIGHT_TEXT", "#1e1e1e")
LIGHT_MUTED_TEXT = THEME_VARS.get("LIGHT_MUTED_TEXT", "#555555")
LIGHT_BORDER = THEME_VARS.get("LIGHT_BORDER", "#cccccc")


# --- DARK THEME QSS ---
DARK_QSS = load_qss("dark.qss")

# --- LIGHT THEME QSS ---
LIGHT_QSS = load_qss("light.qss")

# Default export (for backward compatibility)
GLOBAL_QSS = DARK_QSS

# Define primary button styles
STYLE_SYNC_RUN = load_qss("sync_run.qss")
STYLE_SYNC_STOP = load_qss("sync_stop.qss")

# Define shared button styles for the Start/Cancel button
STYLE_SCAN_START = load_qss("scan_start.qss")
STYLE_SCAN_CANCEL = load_qss("scan_cancel.qss")

SHARED_BUTTON_STYLE = load_qss("shared_button.qss")

# --- Consistent Main Action Button Styles ---
STYLE_START_ACTION = load_qss("shared_button.qss")
STYLE_STOP_ACTION = load_qss("stop_action.qss")
# -------------------------------------------
