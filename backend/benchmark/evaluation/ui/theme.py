"""The inspector's dark stylesheet and small styled-widget helpers.

One stylesheet applied to the window, rather than per-widget ``setStyleSheet``
calls scattered through the build code (the old dashboard used unstyled default
Qt chrome with one inline monospace style). Colours come from
``constants.user_interface``, which derives them from the same two figure
background colours ``bench_anime_stitch.py`` plots with, so embedded matplotlib
canvases sit flush in their panels instead of floating in a differently-tinted
box.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QFrame, QLabel, QWidget

from ..constants.user_interface import (
    COL_ACCENT,
    COL_ACCENT_DIM,
    COL_BG,
    COL_BORDER,
    COL_SURFACE,
    COL_SURFACE_HI,
    COL_TEXT,
    COL_TEXT_DIM,
    SCORE_COLORS,
)

STYLESHEET = f"""
QWidget {{
    background: {COL_BG};
    color: {COL_TEXT};
    font-size: 12px;
}}
QMainWindow, QDialog {{ background: {COL_BG}; }}

QLabel {{ background: transparent; }}
QLabel[role="heading"] {{ font-size: 14px; font-weight: 600; color: {COL_TEXT}; }}
QLabel[role="subtle"] {{ color: {COL_TEXT_DIM}; }}
QLabel[role="panelTitle"] {{
    font-weight: 600;
    padding: 3px 6px;
    background: {COL_SURFACE_HI};
    border: 1px solid {COL_BORDER};
    border-radius: 4px;
}}
QLabel[role="mono"] {{ font-family: monospace; color: {COL_TEXT}; }}

QFrame[role="card"] {{
    background: {COL_SURFACE};
    border: 1px solid {COL_BORDER};
    border-radius: 6px;
}}

QGroupBox {{
    background: {COL_SURFACE};
    border: 1px solid {COL_BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding: 8px 6px 6px 6px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {COL_TEXT_DIM};
}}

QPushButton {{
    background: {COL_SURFACE_HI};
    border: 1px solid {COL_BORDER};
    border-radius: 5px;
    padding: 5px 11px;
}}
QPushButton:hover {{ background: #29294a; border-color: {COL_ACCENT_DIM}; }}
QPushButton:pressed {{ background: #32325c; }}
QPushButton:checked {{
    background: {COL_ACCENT_DIM};
    border-color: {COL_ACCENT};
    color: #04141a;
    font-weight: 600;
}}
QPushButton:disabled {{ color: #5a5a72; background: #14141f; }}
QPushButton[role="primary"] {{
    background: {COL_ACCENT_DIM};
    border-color: {COL_ACCENT};
    color: #04141a;
    font-weight: 600;
}}
QPushButton[role="primary"]:hover {{ background: {COL_ACCENT}; }}

QComboBox, QSpinBox, QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {COL_SURFACE_HI};
    border: 1px solid {COL_BORDER};
    border-radius: 5px;
    padding: 4px 6px;
    selection-background-color: {COL_ACCENT_DIM};
}}
QComboBox:hover {{ border-color: {COL_ACCENT_DIM}; }}
QComboBox QAbstractItemView {{
    background: {COL_SURFACE_HI};
    border: 1px solid {COL_BORDER};
    selection-background-color: {COL_ACCENT_DIM};
    outline: none;
}}
QComboBox::drop-down {{ border: none; width: 18px; }}

QCheckBox, QRadioButton {{ spacing: 6px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {COL_BORDER};
    background: {COL_SURFACE_HI};
}}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 7px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {COL_ACCENT};
    border-color: {COL_ACCENT};
}}

QSlider::groove:horizontal {{
    height: 4px; background: {COL_BORDER}; border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {COL_ACCENT_DIM}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 13px; margin: -5px 0;
    background: {COL_ACCENT}; border-radius: 7px;
}}

QTabWidget::pane {{
    border: 1px solid {COL_BORDER};
    border-radius: 6px;
    background: {COL_SURFACE};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {COL_TEXT_DIM};
    padding: 6px 13px;
    border: 1px solid transparent;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}}
QTabBar::tab:hover {{ color: {COL_TEXT}; }}
QTabBar::tab:selected {{
    background: {COL_SURFACE};
    color: {COL_ACCENT};
    border-color: {COL_BORDER};
    border-bottom-color: {COL_SURFACE};
    font-weight: 600;
}}

QListWidget, QTableWidget, QTreeWidget {{
    background: {COL_SURFACE};
    border: 1px solid {COL_BORDER};
    border-radius: 5px;
    outline: none;
}}
QListWidget::item, QTreeWidget::item {{ padding: 3px 5px; border-radius: 3px; }}
QListWidget::item:selected, QTreeWidget::item:selected,
QTableWidget::item:selected {{ background: {COL_ACCENT_DIM}; color: #04141a; }}
QListWidget::item:hover, QTreeWidget::item:hover {{ background: {COL_SURFACE_HI}; }}
QHeaderView::section {{
    background: {COL_SURFACE_HI};
    color: {COL_TEXT_DIM};
    border: none;
    border-right: 1px solid {COL_BORDER};
    border-bottom: 1px solid {COL_BORDER};
    padding: 4px 6px;
    font-weight: 600;
}}
QTableWidget {{ gridline-color: {COL_BORDER}; }}
QTableCornerButton::section {{ background: {COL_SURFACE_HI}; border: none; }}

QGraphicsView {{
    background: #08080f;
    border: 1px solid {COL_BORDER};
    border-radius: 5px;
}}

QSplitter::handle {{ background: {COL_BORDER}; }}
QSplitter::handle:horizontal {{ width: 3px; }}
QSplitter::handle:vertical {{ height: 3px; }}
QSplitter::handle:hover {{ background: {COL_ACCENT_DIM}; }}

QScrollBar:vertical, QScrollBar:horizontal {{
    background: transparent; border: none;
}}
QScrollBar:vertical {{ width: 10px; }}
QScrollBar:horizontal {{ height: 10px; }}
QScrollBar::handle {{ background: #33334f; border-radius: 5px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: {COL_ACCENT_DIM}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none; border: none; height: 0; width: 0;
}}

QToolTip {{
    background: {COL_SURFACE_HI};
    color: {COL_TEXT};
    border: 1px solid {COL_ACCENT_DIM};
    padding: 4px;
}}

QStatusBar {{ background: {COL_SURFACE}; border-top: 1px solid {COL_BORDER}; }}
QStatusBar::item {{ border: none; }}
QProgressBar {{
    background: {COL_SURFACE_HI};
    border: 1px solid {COL_BORDER};
    border-radius: 5px;
    text-align: center;
    height: 14px;
}}
QProgressBar::chunk {{ background: {COL_ACCENT_DIM}; border-radius: 4px; }}
"""


def apply_theme(widget: QWidget) -> None:
    widget.setStyleSheet(STYLESHEET)


def heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "heading")
    return label


def subtle(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "subtle")
    return label


def mono(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "mono")
    label.setFont(QFont("monospace"))
    return label


def panel_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "panelTitle")
    return label


def card() -> QFrame:
    frame = QFrame()
    frame.setProperty("role", "card")
    return frame


def score_color(score: int) -> QColor:
    return QColor(SCORE_COLORS.get(score, COL_TEXT_DIM))


def score_chip_style(score: int) -> str:
    """Inline style for a 0-4 score button, so the colour ramp is visible on
    the buttons themselves — at a ~28 s/test pace the colour is read, not the
    digit."""
    color = SCORE_COLORS.get(score, COL_BORDER)
    return (
        f"QPushButton {{ border: 1px solid {COL_BORDER}; border-radius: 4px;"
        f" background: {COL_SURFACE_HI}; color: {COL_TEXT_DIM}; font-weight: 600; }}"
        f"QPushButton:hover {{ border-color: {color}; color: {color}; }}"
        f"QPushButton:checked {{ background: {color}; color: #08080f; border-color: {color}; }}"
    )
