"""Theme application (dark/light QSS, density, font scale) and toggling.

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import json
import os

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QWidget

from ...styles import (
    COMPACT_DENSITY_QSS,
    DARK_ACCENT_COLOR,
    LIGHT_ACCENT_COLOR,
    SPACIOUS_DENSITY_QSS,
    compute_accent_vars,
    load_qss_with_overrides,
    load_user_qss_override,
)


class _ThemeMixin:
    """Applies the dark/light stylesheet and handles manual theme toggling."""

    def set_application_theme(self, theme_name):
        prefs = {}
        if hasattr(self, "cached_creds") and self.cached_creds:
            prefs = self.cached_creds.get("preferences", {})

        density = prefs.get("ui_density", "Comfortable")

        if theme_name == "dark":
            accent_color = prefs.get("accent_color_dark", DARK_ACCENT_COLOR)
            overrides = compute_accent_vars(accent_color, "DARK")  # pyrefly: ignore [bad-argument-type]
            qss = load_qss_with_overrides("dark.qss", overrides)
            self.current_theme = "dark"
            hover_bg = "#5f646c"
            pressed_bg = accent_color
            header_label_color = "white"
            header_widget_bg = "#2d2d30"
        elif theme_name == "light":
            accent_color = prefs.get("accent_color_light", LIGHT_ACCENT_COLOR)
            overrides = compute_accent_vars(accent_color, "LIGHT")  # pyrefly: ignore [bad-argument-type]
            qss = load_qss_with_overrides("light.qss", overrides)
            self.current_theme = "light"
            hover_bg = "#cccccc"
            pressed_bg = accent_color
            header_label_color = "#1e1e1e"
            header_widget_bg = "#ffffff"
        else:
            return

        if density == "Compact":
            qss += COMPACT_DENSITY_QSS
        elif density == "Spacious":
            qss += SPACIOUS_DENSITY_QSS

        font_scale = prefs.get("font_scale", 100)
        app_zoom = prefs.get("app_zoom", 0)  # extra zoom offset in percent
        effective_scale = font_scale + app_zoom
        if effective_scale != 100:
            scaled_pt = max(7, int(10 * effective_scale / 100))
            QApplication.instance().setFont(QFont("Segoe UI", scaled_pt))  # pyrefly: ignore [missing-attribute]
        else:
            QApplication.instance().setFont(QFont("Segoe UI", 10))  # pyrefly: ignore [missing-attribute]

        # §3.16 — append user custom QSS override if present
        qss += load_user_qss_override()
        self.setStyleSheet(qss) if "PYTEST_CURRENT_TEST" in os.environ else QApplication.instance().setStyleSheet(qss)  # pyrefly: ignore [missing-attribute]

        header_widget = self.findChild(QWidget, "header_widget")
        if header_widget:
            header_widget.setStyleSheet(
                f"background-color: {header_widget_bg}; padding: 10px; border-bottom: 2px solid {accent_color};"
            )
            title_label = self.title_label
            if title_label:
                account_name = self.cached_creds.get("account_name", "Authenticated User")
                title_label.setText(f"Image Database and Toolkit - {account_name}")
                title_label.setStyleSheet(f"color: {header_label_color}; font-size: 18pt; font-weight: bold;")

        self.settings_button.setStyleSheet(
            f"""
            QPushButton#settings_button {{
                background-color: transparent;
                border: none;
                padding: 5px;
                border-radius: 18px;
            }}
            QPushButton#settings_button:hover {{
                background-color: {hover_bg};
            }}
            QPushButton#settings_button:pressed {{
                background-color: {pressed_bg};
            }}
        """
        )

        # Sync theme toggle icon
        if hasattr(self, "_theme_toggle_btn"):
            self._theme_toggle_btn.setText("☀" if theme_name == "dark" else "🌙")

    def _toggle_theme(self) -> None:
        """Manually toggle dark↔light theme, overriding the OS preference."""
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.set_application_theme(new_theme)
        # Persist the manual preference so the OS follow-OS handler backs off.
        if self.vault_manager is not None:
            try:
                creds = self.vault_manager.load_account_credentials()
                creds["theme"] = new_theme
                self.vault_manager.save_data(json.dumps(creds))
                self.cached_creds = creds
            except Exception:
                pass


__all__ = ["_ThemeMixin"]
