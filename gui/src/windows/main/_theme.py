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
    BackgroundCanvasController,
    BackgroundConfig,
    compute_accent_vars,
    generate_glassmorphism_qss,
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

        # §2.34/§2.35 — background canvas and glassmorphism styling (#440)
        bg_data = prefs.get("background_config", {})
        if bg_data:
            bg_config = BackgroundConfig.from_dict(bg_data)
            BackgroundCanvasController.instance().set_config(bg_config)
            qss += generate_glassmorphism_qss(bg_config, is_dark=(theme_name == "dark"))

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

    def apply_theme_pack(self, pack) -> None:
        """Apply a #437 ThemePack onto the existing $VAR QSS system (hybrid
        migration, round-1 answer): resolve the pack to the QSS var names
        theme.qss already consumes, load the base stylesheet with those
        overrides, then append density/typography/shadow/raw-QSS."""
        from gui.src.theming.resolve import resolve_colors, resolve_to_qss_vars
        from gui.src.styles import COMPACT_DENSITY_QSS, SPACIOUS_DENSITY_QSS, load_qss_with_overrides

        qss_name = f"{pack.base}.qss"
        overrides = resolve_to_qss_vars(pack)
        qss = load_qss_with_overrides(qss_name, overrides)
        self.current_theme = pack.base

        mode = getattr(pack.density, "mode", "comfortable")
        if mode == "compact":
            qss += COMPACT_DENSITY_QSS
        elif mode == "spacious":
            qss += SPACIOUS_DENSITY_QSS

        # Typography: scale percent maps onto the existing font path.
        scale = getattr(pack.typography, "scale_percent", 100)
        if scale != 100:
            scaled_pt = max(7, int(10 * scale / 100))
            QApplication.instance().setFont(QFont("Segoe UI", scaled_pt))
        else:
            QApplication.instance().setFont(QFont("Segoe UI", 10))

        # Raw QSS (expert escape hatch) then the user override hook.
        raw = getattr(pack, "raw_qss", None)
        if raw:
            qss += "\n" + raw
        qss += load_user_qss_override()

        self.setStyleSheet(qss) if "PYTEST_CURRENT_TEST" in os.environ else QApplication.instance().setStyleSheet(qss)

        # Header restyle mirrors set_application_theme's behavior for the
        # resolved accent/window colors.
        header_widget = self.findChild(QWidget, "header_widget")
        if header_widget:
            resolved = resolve_colors(pack)
            accent = resolved.accent
            window_bg = resolved.window_bg
            text = resolved.text
            header_widget.setStyleSheet(
                f"background-color: {window_bg}; padding: 10px; border-bottom: 2px solid {accent};"
            )
            title_label = getattr(self, "title_label", None)
            if title_label is not None:
                title_label.setStyleSheet(f"color: {text}; font-size: 18pt; font-weight: bold;")

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
