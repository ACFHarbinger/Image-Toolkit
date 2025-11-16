#pragma once

#include <QString>
#include <QColor>

class QWidget;

/**
 * @brief Manages application themes, stylesheets, and style helper functions.
 * Equivalent to style.py
 */
namespace Style {

    /**
     * @brief Creates and applies a QGraphicsDropShadowEffect to a given widget.
     */
    void applyShadowEffect(QWidget* widget, 
                           const QColor& color = QColor("#000000"), 
                           int radius = 10, 
                           int x_offset = 0, 
                           int y_offset = 4);

    // --- THEME DEFINITIONS ---
    extern const QString DARK_ACCENT_COLOR;
    extern const QString DARK_ACCENT_HOVER;
    extern const QString DARK_ACCENT_PRESSED;
    extern const QString DARK_ACCENT_MUTED;
    extern const QString DARK_BG;
    extern const QString DARK_SECONDARY_BG;
    extern const QString DARK_TEXT;
    extern const QString DARK_MUTED_TEXT;
    extern const QString DARK_BORDER;

    extern const QString LIGHT_ACCENT_COLOR;
    extern const QString LIGHT_ACCENT_HOVER;
    extern const QString LIGHT_ACCENT_PRESSED;
    extern const QString LIGHT_BG;
    extern const QString LIGHT_SECONDARY_BG;
    extern const QString LIGHT_TEXT;
    extern const QString LIGHT_MUTED_TEXT;
    extern const QString LIGHT_BORDER;

    // --- QSS STRINGS ---
    extern const QString DARK_QSS;
    extern const QString LIGHT_QSS;
    extern const QString GLOBAL_QSS; // Default export

    // --- Special Button Styles ---
    extern const QString STYLE_SYNC_RUN;
    extern const QString STYLE_SYNC_STOP;

} // namespace Style