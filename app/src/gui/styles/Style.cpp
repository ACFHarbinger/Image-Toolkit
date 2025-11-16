#include "Style.h"
#include <QWidget>
#include <QColor>
#include <QGraphicsDropShadowEffect>

namespace Style {

/**
 * @brief Creates and applies a QGraphicsDropShadowEffect to a given widget.
 */
void applyShadowEffect(QWidget* widget, const QColor& color, int radius, int x_offset, int y_offset)
{
    QGraphicsDropShadowEffect* shadow = new QGraphicsDropShadowEffect(widget);
    
    // 1. Set the color
    shadow->setColor(color);
    
    // 2. Set the blur radius
    shadow->setBlurRadius(radius);
    
    // 3. Set the offset
    shadow->setOffset(x_offset, y_offset);
    
    // 4. Apply the effect
    widget->setGraphicsEffect(shadow);
}


// --- THEME DEFINITIONS ---
// Dark Theme
const QString DARK_ACCENT_COLOR = "#00bcd4";
const QString DARK_ACCENT_HOVER = "#0097a7";
const QString DARK_ACCENT_PRESSED = "#00838f";
const QString DARK_ACCENT_MUTED = "#3e3e3e";
const QString DARK_BG = "#1e1e1e";
const QString DARK_SECONDARY_BG = "#2d2d30";
const QString DARK_TEXT = "#cccccc";
const QString DARK_MUTED_TEXT = "#888888";
const QString DARK_BORDER = "#3e3e3e";

// Light Theme
const QString LIGHT_ACCENT_COLOR = "#007AFF";
const QString LIGHT_ACCENT_HOVER = "#0056b3";
const QString LIGHT_ACCENT_PRESSED = "#004085";
const QString LIGHT_BG = "#f5f5f5";
const QString LIGHT_SECONDARY_BG = "#ffffff";
const QString LIGHT_TEXT = "#1e1e1e";
const QString LIGHT_MUTED_TEXT = "#555555";
const QString LIGHT_BORDER = "#cccccc";


// --- DARK THEME QSS ---
// We use QString::arg() to substitute the color variables, just like Python's f-strings.
const QString DARK_QSS = QString(R"(
    /* --- DARK THEME STYLE SHEET (Cyan Accent) --- */
    QWidget, QMainWindow, QDialog {
        background-color: %1;
        color: %2;
        font-family: 'Segoe UI', 'Arial', sans-serif;
        font-size: 10pt;
    }
    QPushButton {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 %3, stop: 1 %4);
        color: white;
        border: none;
        padding: 10px 18px;
        border-radius: 6px;
        font-weight: 600;
    }
    QPushButton:hover { background: %3; }
    QPushButton:pressed { background: %5; padding-top: 12px; padding-bottom: 8px; }
    QPushButton:disabled { background-color: %6; color: %7; }
    QTabWidget::pane { border: 1px solid %8; background-color: %1; border-radius: 8px; }
    QTabBar::tab {
        background: %9; color: #aaaaaa; padding: 10px 20px;
        border: none; border-top-left-radius: 6px; border-top-right-radius: 6px;
        margin-right: 2px;
    }
    QTabBar::tab:selected { background: %1; color: %3; border-bottom: 2px solid %3; font-weight: bold; }
    QTabBar::tab:hover:!selected { background: %8; color: %2; }
    QLineEdit, QComboBox, QSpinBox, QTextEdit {
        background-color: %9; color: %2; border: 1px solid %8;
        padding: 8px; border-radius: 4px;
        selection-background-color: %3; selection-color: white;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
        border: 1px solid %3; background-color: #363639;
    }
    QGroupBox { border: 1px solid %8; margin-top: 25px; border-radius: 8px; padding-top: 15px; }
    QGroupBox::title {
        subcontrol-origin: margin; subcontrol-position: top center;
        padding: 0 12px; background-color: %3; color: white;
        font-size: 11pt; border-radius: 4px;
    }
    QLabel { color: %2; background-color: transparent; }
    QWidget#header_widget { background-color: %9; border-bottom: 2px solid %3; }
)")
.arg(DARK_BG)               // %1
.arg(DARK_TEXT)             // %2
.arg(DARK_ACCENT_COLOR)     // %3
.arg(DARK_ACCENT_HOVER)     // %4
.arg(DARK_ACCENT_PRESSED)   // %5
.arg(DARK_ACCENT_MUTED)     // %6
.arg(DARK_MUTED_TEXT)       // %7
.arg(DARK_BORDER)           // %8
.arg(DARK_SECONDARY_BG);    // %9


// --- LIGHT THEME QSS ---
const QString LIGHT_QSS = QString(R"(
    /* --- LIGHT THEME STYLE SHEET (Blue Accent) --- */
    QWidget, QMainWindow, QDialog {
        background-color: %1;
        color: %2;
        font-family: 'Segoe UI', 'Arial', sans-serif;
        font-size: 10pt;
    }
    QPushButton {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 %3, stop: 1 %4);
        color: white; border: 1px solid %4;
        padding: 10px 18px; border-radius: 6px; font-weight: 600;
    }
    QPushButton:hover { background: %3; }
    QPushButton:pressed { background: %5; padding-top: 12px; padding-bottom: 8px; }
    QPushButton:disabled { background-color: %8; color: %7; border-color: %8; }
    QTabWidget::pane { border: 1px solid %8; background-color: %1; border-radius: 8px; }
    QTabBar::tab {
        background: %9; color: %2; padding: 10px 20px;
        border: none; border-top-left-radius: 6px; border-top-right-radius: 6px;
        margin-right: 2px;
    }
    QTabBar::tab:selected { background: %1; color: %3; border-bottom: 2px solid %3; font-weight: bold; }
    QTabBar::tab:hover:!selected { background: %8; color: %2; }
    QLineEdit, QComboBox, QSpinBox, QTextEdit {
        background-color: %9; color: %2; border: 1px solid %8;
        padding: 8px; border-radius: 4px;
        selection-background-color: %3; selection-color: white;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
        border: 1px solid %3; background-color: %9;
    }
    QGroupBox { border: 1px solid %8; margin-top: 25px; border-radius: 8px; padding-top: 15px; }
    QGroupBox::title {
        subcontrol-origin: margin; subcontrol-position: top center;
        padding: 0 12px; background-color: %3; color: white;
        font-size: 11pt; border-radius: 4px;
    }
    QLabel { color: %2; background-color: transparent; }
    QWidget#header_widget { background-color: %10; border-bottom: 2px solid %3; }
)")
.arg(LIGHT_BG)              // %1
.arg(LIGHT_TEXT)            // %2
.arg(LIGHT_ACCENT_COLOR)    // %3
.arg(LIGHT_ACCENT_HOVER)    // %4
.arg(LIGHT_ACCENT_PRESSED)  // %5
.arg(LIGHT_BORDER)          // %6 (Note: %6 is unused, this is a gap)
.arg(LIGHT_MUTED_TEXT)      // %7
.arg(LIGHT_BORDER)          // %8 (Used again)
.arg(LIGHT_SECONDARY_BG)    // %9
.arg(DARK_SECONDARY_BG);    // %10 (Uses dark bg for header)


// Default export
const QString GLOBAL_QSS = DARK_QSS;

// --- Special Button Styles ---
const QString STYLE_SYNC_RUN = QStringLiteral(R"(
    QPushButton { background:#2ecc71; color:white; padding:12px 16px;
                    font-size:14pt; border-radius:8px; font-weight:bold; }
    QPushButton:hover { background:#1e8449; }
    QPushButton:disabled { background:#4f545c; color:#a0a0a0; }
)");

const QString STYLE_SYNC_STOP = QStringLiteral(R"(
    QPushButton { background:#e74c3c; color:white; padding:12px 16px;
                    font-size:14pt; border-radius:8px; font-weight:bold; }
    QPushButton:hover { background:#c0392b; }
    QPushButton:disabled { background:#4f545c; color:#a0a0a0; }
)");


} // namespace Style