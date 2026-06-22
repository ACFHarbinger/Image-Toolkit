import os
import re

from string import Template
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


def parse_theme_vars() -> dict:
    """Parses variables from theme.qss file.

    Returns:
        dict: A dictionary containing the theme variables.
    """
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


def load_qss(filename: str) -> str:
    """Loads QSS content from a file and performs variable substitution.

    Args:
        filename (str): The name of the QSS file to load.

    Returns:
        str: The QSS content with variables substituted.
    """
    path = os.path.join(os.path.dirname(__file__), "qss", filename)
    try:
        with open(path, "r") as f:
            content = f.read()
            # Perform variable substitution
            return Template(content).safe_substitute(THEME_VARS)
    except FileNotFoundError:
        print(f"Warning: QSS file not found: {path}")
        return ""


def load_qss_with_overrides(filename: str, overrides: dict | None = None) -> str:
    """Loads QSS with runtime variable overrides merged into THEME_VARS.

    Args:
        filename (str): The name of the QSS file to load.
        overrides (dict, optional): A dictionary of variables to override. Defaults to None.

    Returns:
        str: The QSS content with variables substituted.
    """
    path = os.path.join(os.path.dirname(__file__), "qss", filename)
    try:
        with open(path, "r") as f:
            content = f.read()
        vars_to_use = dict(THEME_VARS)
        if overrides:
            vars_to_use.update(overrides)
        return Template(content).safe_substitute(vars_to_use)
    except FileNotFoundError:
        print(f"Warning: QSS file not found: {path}")
        return ""


def compute_accent_vars(accent_hex: str, theme_prefix: str = "DARK") -> dict:
    """Compute accent color variants for theming.

    Args:
        accent_hex (str): The hex color to use for the accent.
        theme_prefix (str, optional): The prefix to use for the theme variables. Defaults to "DARK".

    Returns:
        dict: A dictionary containing the accent color variants.
    """
    c = QColor(accent_hex)
    if not c.isValid():
        c = QColor(THEME_VARS.get(f"{theme_prefix}_ACCENT_COLOR", "#00bcd4"))
    return {
        f"{theme_prefix}_ACCENT_COLOR": c.name(),
        f"{theme_prefix}_ACCENT_HOVER": c.darker(115).name(),
        f"{theme_prefix}_ACCENT_PRESSED": c.darker(132).name(),
    }


def load_user_qss_override() -> str:
    """Return contents of ~/.image-toolkit/user_theme.qss, or '' if absent.

    Returns:
        str: The contents of the user_theme.qss file.
    """
    path = os.path.expanduser("~/.image-toolkit/user_theme.qss")
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


# --- Density override snippets (appended after base theme QSS) ---
COMPACT_DENSITY_QSS = """
QPushButton { padding: 5px 10px; border-radius: 4px; }
QComboBox { padding: 3px 6px; }
QLineEdit, QSpinBox, QDoubleSpinBox { padding: 3px 5px; }
QGroupBox { padding-top: 6px; margin-top: 4px; }
"""

SPACIOUS_DENSITY_QSS = """
QPushButton { padding: 14px 26px; border-radius: 8px; }
QComboBox { padding: 10px 14px; }
QLineEdit, QSpinBox, QDoubleSpinBox { padding: 10px 8px; }
QGroupBox { padding-top: 16px; margin-top: 8px; }
"""


def apply_shadow_effect(
    widget, color_hex="#000000", radius: int = 10, x_offset: int = 0, y_offset: int = 4
) -> QGraphicsDropShadowEffect:
    """Creates and applies a QGraphicsDropShadowEffect to a given widget.

    Args:
        widget: The widget to apply the shadow effect to.
        color_hex (str, optional): The hex color to use for the shadow. Defaults to "#000000".
        radius (int, optional): The radius of the shadow. Defaults to 10.
        x_offset (int, optional): The x offset of the shadow. Defaults to 0.
        y_offset (int, optional): The y offset of the shadow. Defaults to 4.

    Returns:
        QGraphicsDropShadowEffect: The applied shadow effect.
    """
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
