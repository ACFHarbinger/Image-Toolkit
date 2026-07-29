"""Appearance section (theme/accent/zoom) UI construction and helper methods.

Extracted from ``settings_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
)


class _AppearanceMixin:
    """Builds the Appearance groupbox and provides its supporting helpers."""

    def _build_appearance_section(self) -> QGroupBox:
        appearance_groupbox = QGroupBox("Appearance")
        appearance_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        appearance_layout = QFormLayout(appearance_groupbox)
        appearance_layout.setContentsMargins(10, 10, 10, 10)

        # App Theme Selection
        theme_layout = QHBoxLayout()
        self.dark_theme_radio = QRadioButton("Dark Theme")
        self.light_theme_radio = QRadioButton("Light Theme")

        self.dark_theme_radio.setMinimumWidth(180)
        self.light_theme_radio.setMinimumWidth(180)
        self.dark_theme_radio.setStyleSheet("QRadioButton { min-width: 180px; padding: 4px; }")
        self.light_theme_radio.setStyleSheet("QRadioButton { min-width: 180px; padding: 4px; }")

        # Set the radio button based on the loaded initial theme
        if self.initial_theme == "light":
            self.light_theme_radio.setChecked(True)
        else:
            self.dark_theme_radio.setChecked(True)

        theme_layout.addWidget(self.dark_theme_radio)
        theme_layout.addWidget(self.light_theme_radio)
        theme_layout.addStretch()
        appearance_layout.addRow("App Theme:", theme_layout)

        # Dark accent colour swatch + picker
        dark_accent_row = QHBoxLayout()
        self.dark_accent_swatch = QPushButton()
        self.dark_accent_swatch.setFixedSize(180, 22)
        self.dark_accent_swatch.setToolTip("Click to pick a custom accent colour for the dark theme")
        self._update_swatch(self.dark_accent_swatch, self.pref_accent_dark)
        self.dark_accent_swatch.clicked.connect(lambda: self._pick_accent_color("dark"))
        dark_accent_reset = QPushButton("Reset")
        dark_accent_reset.setFixedWidth(100)
        dark_accent_reset.clicked.connect(lambda: self._reset_accent("dark"))
        dark_accent_row.addWidget(self.dark_accent_swatch)
        dark_accent_row.addWidget(dark_accent_reset)
        dark_accent_row.addStretch()
        appearance_layout.addRow("Dark Theme Accent Colour:", dark_accent_row)

        # Light accent colour swatch + picker
        light_accent_row = QHBoxLayout()
        self.light_accent_swatch = QPushButton()
        self.light_accent_swatch.setFixedSize(180, 22)
        self.light_accent_swatch.setToolTip("Click to pick a custom accent colour for the light theme")
        self._update_swatch(self.light_accent_swatch, self.pref_accent_light)
        self.light_accent_swatch.clicked.connect(lambda: self._pick_accent_color("light"))
        light_accent_reset = QPushButton("Reset")
        light_accent_reset.setFixedWidth(100)
        light_accent_reset.clicked.connect(lambda: self._reset_accent("light"))
        light_accent_row.addWidget(self.light_accent_swatch)
        light_accent_row.addWidget(light_accent_reset)
        light_accent_row.addStretch()
        appearance_layout.addRow("Light Theme Accent Colour:", light_accent_row)

        # Font scale
        self.font_scale_spinbox = QSpinBox()
        self.font_scale_spinbox.setRange(80, 150)
        self.font_scale_spinbox.setSingleStep(10)
        self.font_scale_spinbox.setSuffix(" %")
        self.font_scale_spinbox.setValue(self.pref_font_scale)
        self.font_scale_spinbox.setToolTip(
            "Scale all UI text relative to the base 10pt size (applied on next theme reload)"
        )
        appearance_layout.addRow("Font Scale:", self.font_scale_spinbox)

        # UI density
        self.ui_density_combo = QComboBox()
        self.ui_density_combo.addItems(["Compact", "Comfortable", "Spacious"])
        self.ui_density_combo.setCurrentText(self.pref_ui_density)
        self.ui_density_combo.setToolTip("Controls button padding and widget spacing throughout the app")
        appearance_layout.addRow("UI Density:", self.ui_density_combo)

        # App Zoom row
        zoom_row = QHBoxLayout()
        btn_zoom_out = QPushButton("Zoom −")
        btn_zoom_out.setFixedWidth(80)
        btn_zoom_out.setToolTip("Decrease the global app zoom by 10%  (Ctrl + Scroll Down)")
        btn_zoom_out.clicked.connect(self._zoom_out)
        btn_zoom_in = QPushButton("Zoom +")
        btn_zoom_in.setFixedWidth(80)
        btn_zoom_in.setToolTip("Increase the global app zoom by 10%  (Ctrl + Scroll Up)")
        btn_zoom_in.clicked.connect(self._zoom_in)
        self._zoom_label = QLabel(self._zoom_label_text())
        self._zoom_label.setToolTip(
            "Current extra zoom offset on top of Font Scale.\nDefault / Reset shortcut: set both buttons to 0."
        )
        zoom_row.addWidget(btn_zoom_out)
        zoom_row.addWidget(btn_zoom_in)
        zoom_row.addSpacing(8)
        zoom_row.addWidget(self._zoom_label)
        zoom_row.addStretch()
        appearance_layout.addRow("App Zoom:", zoom_row)

        # Preview button row
        preview_row = QHBoxLayout()
        btn_preview_appearance = QPushButton("Preview")
        btn_preview_appearance.setFixedWidth(90)
        btn_preview_appearance.setToolTip("Apply the current accent/density settings live (does not save)")
        btn_preview_appearance.clicked.connect(self._preview_appearance)
        preview_row.addWidget(btn_preview_appearance)
        preview_row.addStretch()
        appearance_layout.addRow("", preview_row)

        return appearance_groupbox

    # ------------------------------------------------------------------
    # --- Appearance Helpers -------------------------------------------
    # ------------------------------------------------------------------

    def _update_swatch(self, button, hex_color):
        """Paint a colour swatch onto a QPushButton."""
        c = QColor(hex_color)
        if not c.isValid():
            c = QColor("#888888")
        r, g, b = c.red(), c.green(), c.blue()
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        text_color = "black" if luminance > 0.5 else "white"
        button.setStyleSheet(
            f"QPushButton {{ background-color: {c.name()}; border: 1px solid #888; border-radius: 3px; color: {text_color}; font-weight: bold; }}"
        )
        button.setText(hex_color.upper())

    def _pick_accent_color(self, theme):
        """Open QColorDialog and update the swatch + stored preference."""
        current = self.pref_accent_dark if theme == "dark" else self.pref_accent_light
        initial = QColor(current)
        color = QColorDialog.getColor(
            initial,
            self,
            f"Choose {theme.capitalize()} Theme Accent Colour",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if color.isValid():
            hex_val = color.name()
            if theme == "dark":
                self.pref_accent_dark = hex_val
                self._update_swatch(self.dark_accent_swatch, hex_val)
            else:
                self.pref_accent_light = hex_val
                self._update_swatch(self.light_accent_swatch, hex_val)

    def _reset_accent(self, theme):
        """Reset accent colour to the built-in default."""
        default = "#00bcd4" if theme == "dark" else "#007AFF"
        if theme == "dark":
            self.pref_accent_dark = default
            self._update_swatch(self.dark_accent_swatch, default)
        else:
            self.pref_accent_light = default
            self._update_swatch(self.light_accent_swatch, default)

    def _zoom_label_text(self) -> str:
        """Return a human-readable string for the current app_zoom offset."""
        z = self.pref_app_zoom
        sign = "+" if z >= 0 else ""
        return f"Current: {sign}{z}%"

    def _zoom_in(self) -> None:
        """Increase pref_app_zoom by 10% (max +100%) and apply live."""
        if self.pref_app_zoom >= 100:
            return
        self.pref_app_zoom += 10
        self._zoom_label.setText(self._zoom_label_text())
        if self.main_window_ref and hasattr(self.main_window_ref, "zoom_in"):
            self.main_window_ref.zoom_in()
            # Keep pref in sync with what main window actually did
            mw_prefs = getattr(self.main_window_ref, "cached_creds", {}).get("preferences", {})
            self.pref_app_zoom = mw_prefs.get("app_zoom", self.pref_app_zoom)
            self._zoom_label.setText(self._zoom_label_text())

    def _zoom_out(self) -> None:
        """Decrease pref_app_zoom by 10% (min −50%) and apply live."""
        if self.pref_app_zoom <= -50:
            return
        self.pref_app_zoom -= 10
        self._zoom_label.setText(self._zoom_label_text())
        if self.main_window_ref and hasattr(self.main_window_ref, "zoom_out"):
            self.main_window_ref.zoom_out()
            mw_prefs = getattr(self.main_window_ref, "cached_creds", {}).get("preferences", {})
            self.pref_app_zoom = mw_prefs.get("app_zoom", self.pref_app_zoom)
            self._zoom_label.setText(self._zoom_label_text())

    def _preview_appearance(self):
        """Apply current accent/density/font settings live without saving."""
        if not self.main_window_ref:
            return
        if not hasattr(self.main_window_ref, "cached_creds") or not self.main_window_ref.cached_creds:
            return
        prefs = dict(self.main_window_ref.cached_creds.get("preferences", {}))
        prefs["accent_color_dark"] = self.pref_accent_dark
        prefs["accent_color_light"] = self.pref_accent_light
        prefs["font_scale"] = self.font_scale_spinbox.value()
        prefs["ui_density"] = self.ui_density_combo.currentText()
        self.main_window_ref.cached_creds["preferences"] = prefs
        theme = self.main_window_ref.current_theme
        self.main_window_ref.set_application_theme(theme)


__all__ = ["_AppearanceMixin"]
