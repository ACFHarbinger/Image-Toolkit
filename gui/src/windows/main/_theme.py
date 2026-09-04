"""Theme application (dark/light QSS, density, font scale) and toggling.

Extracted from ``main_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import json
import os

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from ...styles import (
    COMPACT_DENSITY_QSS,
    DARK_ACCENT_COLOR,
    DARK_BG,
    DARK_BORDER,
    DARK_MUTED_TEXT,
    DARK_SECONDARY_BG,
    DARK_TEXT,
    LIGHT_ACCENT_COLOR,
    LIGHT_BG,
    LIGHT_BORDER,
    LIGHT_MUTED_TEXT,
    LIGHT_SECONDARY_BG,
    LIGHT_TEXT,
    SPACIOUS_DENSITY_QSS,
    BackgroundCanvasController,
    BackgroundConfig,
    compute_accent_vars,
    generate_glassmorphism_qss,
    load_qss_with_overrides,
    load_user_qss_override,
)


def _build_palette(
    theme_name: str,
    accent_color: str,
    *,
    bg: str | None = None,
    surface: str | None = None,
    text: str | None = None,
    muted: str | None = None,
    border: str | None = None,
) -> QPalette:
    """Build a QPalette matching the QSS theme colors.

    Frozen (PyInstaller) Qt ships no KDE/GTK platform-theme plugin, so
    ``QApplication.palette()`` otherwise stays Qt's built-in *light*
    default even under the dark QSS. Widgets that read the palette
    directly instead of relying on the stylesheet (e.g. ``OptionalField``)
    then render with the wrong colors. Setting the palette explicitly here
    keeps them in sync with the active theme regardless of platform.

    Explicit colors (from a resolved #437 ThemePack) win; otherwise fall
    back to the built-in dark/light QSS var defaults.
    """
    if bg is None:
        if theme_name == "dark":
            bg, surface, text, muted, border = DARK_BG, DARK_SECONDARY_BG, DARK_TEXT, DARK_MUTED_TEXT, DARK_BORDER
        else:
            bg, surface, text, muted, border = LIGHT_BG, LIGHT_SECONDARY_BG, LIGHT_TEXT, LIGHT_MUTED_TEXT, LIGHT_BORDER

    palette = QPalette()
    for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Button):
        palette.setColor(role, QColor(bg))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ToolTipText,
    ):
        palette.setColor(role, QColor(text))
    palette.setColor(QPalette.ColorRole.Base, QColor(surface))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(bg))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(surface))
    palette.setColor(QPalette.ColorRole.Mid, QColor(border))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(accent_color))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText, QPalette.ColorRole.Text):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(muted))
    return palette


class _ThemeMixin:
    """Applies the dark/light stylesheet and handles manual theme toggling."""

    def prime_application_palette(self, theme_name: str) -> None:
        """Set the app QPalette for ``theme_name`` before any widgets exist.

        ``MainWindow.__init__`` builds every tab (and so every
        palette-reading widget, e.g. ``OptionalField``) before its own
        ``set_application_theme()`` call runs. On a frozen build with no
        platform-theme plugin, ``QApplication.palette()`` is still Qt's
        light default at that point, so those widgets bake in the wrong
        colors permanently. Call this first, right after ``current_theme``
        is known and before building anything else; the later full
        ``set_application_theme()`` call re-applies the same palette
        (harmlessly) alongside the stylesheet/header/etc.
        """
        prefs = {}
        if hasattr(self, "cached_creds") and self.cached_creds:
            prefs = self.cached_creds.get("preferences", {})
        if theme_name == "dark":
            accent_color = prefs.get("accent_color_dark", DARK_ACCENT_COLOR)
        else:
            accent_color = prefs.get("accent_color_light", LIGHT_ACCENT_COLOR)
        app = QApplication.instance()
        if app is not None:
            app.setPalette(_build_palette(theme_name, accent_color))

    def set_application_theme(self, theme_name):  # noqa: C901
        prefs = {}
        if hasattr(self, "cached_creds") and self.cached_creds:
            prefs = self.cached_creds.get("preferences", {})

        density = prefs.get("ui_density", "Comfortable")

        if theme_name == "dark":
            accent_color = prefs.get("accent_color_dark", DARK_ACCENT_COLOR)
            overrides = compute_accent_vars(accent_color, "DARK")  # pyrefly: ignore [bad-argument-type]
            color_overrides = prefs.get("color_overrides", {})
            if color_overrides and isinstance(color_overrides, dict):
                try:
                    from gui.src.theming.resolve import resolve_colors, to_qss_vars
                    from gui.src.theming.schema import ThemePack

                    pack = ThemePack(name="Active", base="dark", color_overrides=color_overrides)
                    resolved = resolve_colors(pack)
                    overrides.update(to_qss_vars(resolved, prefix="DARK"))
                except Exception:
                    pass
            qss = load_qss_with_overrides("dark.qss", overrides)
            self.current_theme = "dark"
            hover_bg = "#5f646c"
            pressed_bg = accent_color
            header_label_color = "white"
            header_widget_bg = "#2d2d30"
        elif theme_name == "light":
            accent_color = prefs.get("accent_color_light", LIGHT_ACCENT_COLOR)
            overrides = compute_accent_vars(accent_color, "LIGHT")  # pyrefly: ignore [bad-argument-type]
            color_overrides = prefs.get("color_overrides", {})
            if color_overrides and isinstance(color_overrides, dict):
                try:
                    from gui.src.theming.resolve import resolve_colors, to_qss_vars
                    from gui.src.theming.schema import ThemePack

                    pack = ThemePack(name="Active", base="light", color_overrides=color_overrides)
                    resolved = resolve_colors(pack)
                    overrides.update(to_qss_vars(resolved, prefix="LIGHT"))
                except Exception:
                    pass
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
            QApplication.instance().setFont(QFont("Inter", scaled_pt))  # pyrefly: ignore [missing-attribute]
        else:
            QApplication.instance().setFont(QFont("Inter", 10))  # pyrefly: ignore [missing-attribute]

        # §3.16 — append user custom QSS override if present
        qss += load_user_qss_override()

        # §2.34/§2.35 — background canvas and glassmorphism styling (#440)
        bg_data = prefs.get("background_config", {})
        if bg_data:
            bg_config = BackgroundConfig.from_dict(bg_data)
            BackgroundCanvasController.instance().set_config(bg_config)
        else:
            bg_config = BackgroundCanvasController.instance().config

        effective_bg = BackgroundCanvasController.instance().get_effective_image_path()
        if bg_config.glassmorphism_enabled and (bg_config.image_path or effective_bg):
            qss += generate_glassmorphism_qss(bg_config, is_dark=(theme_name == "dark"))

        corner_radius = prefs.get("corner_radius")
        if corner_radius is not None and isinstance(corner_radius, (int, float)):
            qss += f"\nQPushButton, QComboBox, QLineEdit, QSpinBox {{ border-radius: {int(corner_radius)}px; }}\n"

        app = QApplication.instance()
        if app is not None:
            app.setPalette(_build_palette(theme_name, accent_color))
        self.setStyleSheet(qss) if "PYTEST_CURRENT_TEST" in os.environ else app.setStyleSheet(qss)  # pyrefly: ignore [missing-attribute]

        header_widget = self.findChild(QWidget, "header_widget")
        if header_widget:
            if bg_config.glassmorphism_enabled and (bg_config.image_path or effective_bg):
                header_widget_bg = "rgba(16, 18, 22, 0.65)" if theme_name == "dark" else "rgba(255, 255, 255, 0.70)"
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
        from gui.src.styles import COMPACT_DENSITY_QSS, SPACIOUS_DENSITY_QSS, load_qss_with_overrides
        from gui.src.theming.resolve import resolve_colors, resolve_to_qss_vars

        qss_name = f"{pack.base}.qss"
        overrides = resolve_to_qss_vars(pack)
        qss = load_qss_with_overrides(qss_name, overrides)
        self.current_theme = pack.base

        mode = getattr(pack.density, "mode", "comfortable")
        if mode == "compact":
            qss += COMPACT_DENSITY_QSS
        elif mode == "spacious":
            qss += SPACIOUS_DENSITY_QSS

        # Typography: font family and scale percent mapped onto the application font.
        scale = getattr(pack.typography, "scale_percent", 100)
        family = getattr(pack.typography, "font_family", None) or "Inter"
        if scale != 100:
            scaled_pt = max(7, int(10 * scale / 100))
            QApplication.instance().setFont(QFont(family, scaled_pt))
        else:
            QApplication.instance().setFont(QFont(family, 10))

        # Raw QSS (expert escape hatch) then the user override hook.
        raw = getattr(pack, "raw_qss", None)
        if raw:
            qss += "\n" + raw
        qss += load_user_qss_override()

        # Background tokens & glassmorphism styling
        if hasattr(pack, "background") and pack.background:
            BackgroundCanvasController.instance().set_background_tokens(
                pack.background, getattr(pack, "backgrounds", [])
            )
        bg_config = BackgroundCanvasController.instance().config
        effective_bg = BackgroundCanvasController.instance().get_effective_image_path()
        if bg_config.glassmorphism_enabled and (bg_config.image_path or effective_bg):
            qss += generate_glassmorphism_qss(bg_config, is_dark=(pack.base == "dark"))

        resolved = resolve_colors(pack)
        app = QApplication.instance()
        if app is not None:
            app.setPalette(
                _build_palette(
                    pack.base,
                    resolved.accent,
                    bg=resolved.window_bg,
                    surface=resolved.surface,
                    text=resolved.text,
                    muted=resolved.muted_text,
                    border=resolved.border,
                )
            )
        self.setStyleSheet(qss) if "PYTEST_CURRENT_TEST" in os.environ else app.setStyleSheet(qss)

        # Header restyle mirrors set_application_theme's behavior for the
        # resolved accent/window colors.
        header_widget = self.findChild(QWidget, "header_widget")
        if header_widget:
            accent = resolved.accent
            window_bg = resolved.window_bg
            if bg_config.glassmorphism_enabled and (bg_config.image_path or effective_bg):
                window_bg = "rgba(16, 18, 22, 0.65)" if pack.base == "dark" else "rgba(255, 255, 255, 0.70)"
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
