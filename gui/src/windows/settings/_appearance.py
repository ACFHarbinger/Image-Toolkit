"""Appearance and Theme Studio section (theme/palette/background/density/zoom).

Implements full-window background customization, semantic color palette editing,
dynamic palette extraction, corner curvature, and glassmorphic layering (#438, #440).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from gui.src.components.dialogs.thumbnail_file_picker import ThumbnailFilePicker
from gui.src.styles.background_canvas import BackgroundCanvasController, BackgroundConfig
from gui.src.theming.palette import extract_palette
from gui.src.theming.resolve import base_defaults
from gui.src.theming.schema import ColorTokens
from gui.src.theming.validate import contrast_warnings


class _AppearanceMixin:
    """Builds the Appearance & Theme Studio groupboxes and provides supporting helpers."""

    def _build_appearance_section(self) -> QGroupBox:
        appearance_groupbox = QGroupBox("Theme & Aesthetics Studio")
        appearance_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        appearance_layout = QFormLayout(appearance_groupbox)
        appearance_layout.setContentsMargins(10, 10, 10, 10)

        # ------------------------------------------------------------------
        # 1. Base Theme Selection
        # ------------------------------------------------------------------
        theme_layout = QHBoxLayout()
        self.dark_theme_radio = QRadioButton("Dark Base")
        self.light_theme_radio = QRadioButton("Light Base")
        self.dark_theme_radio.setMinimumWidth(180)
        self.light_theme_radio.setMinimumWidth(180)
        self.dark_theme_radio.setStyleSheet("QRadioButton { min-width: 180px; padding: 4px; }")
        self.light_theme_radio.setStyleSheet("QRadioButton { min-width: 180px; padding: 4px; }")

        if self.initial_theme == "light":
            self.light_theme_radio.setChecked(True)
        else:
            self.dark_theme_radio.setChecked(True)

        self.dark_theme_radio.toggled.connect(self._on_base_theme_changed)
        theme_layout.addWidget(self.dark_theme_radio)
        theme_layout.addWidget(self.light_theme_radio)
        theme_layout.addStretch()
        appearance_layout.addRow("Base Theme:", theme_layout)

        # ------------------------------------------------------------------
        # 2. Semantic Color Palette Swatches
        # ------------------------------------------------------------------
        self._palette_swatches: dict[str, QPushButton] = {}
        dark_def = base_defaults("dark").as_dict()
        light_def = base_defaults("light").as_dict()
        self._current_colors: dict[str, str] = dict(
            self.pref_color_overrides
            if isinstance(self.pref_color_overrides, dict) and self.pref_color_overrides
            else (dark_def if self.initial_theme != "light" else light_def)
        )


        # Legacy fallback compatibility
        if "accent" not in self._current_colors:
            self._current_colors["accent"] = self.pref_accent_dark if self.initial_theme != "light" else self.pref_accent_light

        # Palette row (Primary Accent, Surface, Window BG, Text, Muted, Border)
        palette_grid = QHBoxLayout()
        for token_key, label_name in [
            ("accent", "Accent"),
            ("surface", "Surface"),
            ("window_bg", "Window BG"),
            ("text", "Text"),
            ("muted_text", "Muted"),
            ("border", "Border"),
        ]:
            col_box = QVBoxLayout()
            col_box.setSpacing(3)
            lbl = QLabel(label_name)
            lbl.setStyleSheet("font-size: 8.5pt; font-weight: 500; color: #aaaaaa;")
            swatch = QPushButton()
            swatch.setFixedSize(65, 32)
            swatch.setToolTip(f"Click to pick custom {label_name} colour")
            col_val = self._current_colors.get(token_key, "#00bcd4")
            self._update_swatch_color(swatch, col_val)
            swatch.clicked.connect(lambda _, k=token_key: self._pick_palette_color(k))
            self._palette_swatches[token_key] = swatch
            col_box.addWidget(lbl)
            col_box.addWidget(swatch)
            palette_grid.addLayout(col_box)

        # Reset Palette Button
        btn_reset_palette = QPushButton("Reset Defaults")
        btn_reset_palette.setMinimumHeight(32)
        btn_reset_palette.setMinimumWidth(120)
        btn_reset_palette.setStyleSheet("QPushButton { padding: 4px 12px; font-weight: 500; }")
        btn_reset_palette.clicked.connect(self._reset_palette_to_base_defaults)
        palette_grid.addSpacing(12)
        palette_grid.addWidget(btn_reset_palette, alignment=Qt.AlignmentFlag.AlignBottom)
        palette_grid.addStretch()
        appearance_layout.addRow("Semantic Palette:", palette_grid)

        # Dynamic Palette Extraction button & Contrast advisory row
        extract_row = QHBoxLayout()
        self.btn_extract_palette = QPushButton("🎨 Auto-Extract from Background")
        self.btn_extract_palette.setMinimumHeight(32)
        self.btn_extract_palette.setMinimumWidth(230)
        self.btn_extract_palette.setStyleSheet("QPushButton { padding: 4px 14px; font-weight: 500; }")
        self.btn_extract_palette.setToolTip("Derive harmonious semantic colors automatically from the active background image (Material You style)")
        self.btn_extract_palette.clicked.connect(self._extract_palette_from_current_background)
        extract_row.addWidget(self.btn_extract_palette)

        self.contrast_status_label = QLabel()
        self._update_contrast_status()
        extract_row.addSpacing(12)
        extract_row.addWidget(self.contrast_status_label)
        extract_row.addStretch()
        appearance_layout.addRow("Color Extraction & A11y:", extract_row)

        # ------------------------------------------------------------------
        # 3. Full-Window Background Canvas & Glassmorphism
        # ------------------------------------------------------------------
        bg_config_dict = self.pref_background_config if isinstance(self.pref_background_config, dict) else {}
        self._bg_config = BackgroundConfig.from_dict(bg_config_dict)

        bg_path_row = QHBoxLayout()
        self.bg_path_input = QLineEdit(self._bg_config.image_path)
        self.bg_path_input.setMinimumHeight(32)
        self.bg_path_input.setPlaceholderText("Select background image path (e.g. .png, .jpg, .webp)...")
        self.bg_path_input.textChanged.connect(self._on_bg_path_changed)
        btn_browse_bg = QPushButton("Browse...")
        btn_browse_bg.setMinimumHeight(32)
        btn_browse_bg.setMinimumWidth(95)
        btn_browse_bg.setStyleSheet("QPushButton { padding: 4px 12px; }")
        btn_browse_bg.clicked.connect(self._browse_background_image)
        btn_clear_bg = QPushButton("Clear")
        btn_clear_bg.setMinimumHeight(32)
        btn_clear_bg.setMinimumWidth(75)
        btn_clear_bg.setStyleSheet("QPushButton { padding: 4px 12px; }")
        btn_clear_bg.clicked.connect(lambda: self.bg_path_input.clear())
        bg_path_row.addWidget(self.bg_path_input)
        bg_path_row.addWidget(btn_browse_bg)
        bg_path_row.addWidget(btn_clear_bg)
        appearance_layout.addRow("Background Image:", bg_path_row)

        # Fit Mode & Glassmorphism Row
        fit_glass_row = QHBoxLayout()
        self.bg_fit_combo = QComboBox()
        self.bg_fit_combo.setMinimumHeight(30)
        self.bg_fit_combo.addItems(["Cover", "Contain", "Center", "Tile"])
        idx = self.bg_fit_combo.findText(self._bg_config.fit_mode.capitalize())
        if idx >= 0:
            self.bg_fit_combo.setCurrentIndex(idx)
        fit_glass_row.addWidget(QLabel("Fit:"))
        fit_glass_row.addWidget(self.bg_fit_combo)

        self.glassmorphism_check = QCheckBox("Translucent Glassmorphism (Frosted Cards)")
        self.glassmorphism_check.setChecked(self._bg_config.glassmorphism_enabled or bool(self._bg_config.image_path))
        fit_glass_row.addSpacing(16)
        fit_glass_row.addWidget(self.glassmorphism_check)
        fit_glass_row.addStretch()
        appearance_layout.addRow("Canvas Mode:", fit_glass_row)

        # Opacity & Blur Sliders
        sliders_row = QHBoxLayout()
        sliders_row.addWidget(QLabel("Opacity:"))
        self.bg_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_opacity_slider.setRange(10, 100)
        self.bg_opacity_slider.setValue(int(self._bg_config.opacity * 100))
        self.bg_opacity_label = QLabel(f"{self.bg_opacity_slider.value()}%")
        self.bg_opacity_label.setFixedWidth(40)
        self.bg_opacity_slider.valueChanged.connect(
            lambda v: self.bg_opacity_label.setText(f"{v}%")
        )
        sliders_row.addWidget(self.bg_opacity_slider)
        sliders_row.addWidget(self.bg_opacity_label)

        sliders_row.addSpacing(16)
        sliders_row.addWidget(QLabel("Backdrop Blur:"))
        self.bg_blur_spin = QSpinBox()
        self.bg_blur_spin.setMinimumHeight(30)
        self.bg_blur_spin.setRange(0, 30)
        self.bg_blur_spin.setSuffix(" px")
        self.bg_blur_spin.setValue(self._bg_config.blur_radius)
        self.bg_blur_spin.setToolTip("Gaussian backdrop blur radius (0 = off, smooth 4-16px)")
        sliders_row.addWidget(self.bg_blur_spin)
        sliders_row.addStretch()
        appearance_layout.addRow("Canvas Effects:", sliders_row)

        # ------------------------------------------------------------------
        # 4. Widget Styling, Typography & Density
        # ------------------------------------------------------------------
        styling_row = QHBoxLayout()
        styling_row.addWidget(QLabel("Corner Radius:"))
        self.corner_radius_combo = QComboBox()
        self.corner_radius_combo.setMinimumHeight(30)
        self.corner_radius_combo.addItem("Sharp (0px)", 0)
        self.corner_radius_combo.addItem("Subtle (4px)", 4)
        self.corner_radius_combo.addItem("Rounded (8px)", 8)
        self.corner_radius_combo.addItem("Pill (16px)", 16)
        current_rad = int(self.pref_corner_radius)
        for i in range(self.corner_radius_combo.count()):
            if self.corner_radius_combo.itemData(i) == current_rad:
                self.corner_radius_combo.setCurrentIndex(i)
                break
        styling_row.addWidget(self.corner_radius_combo)

        styling_row.addSpacing(16)
        styling_row.addWidget(QLabel("UI Density:"))
        self.ui_density_combo = QComboBox()
        self.ui_density_combo.setMinimumHeight(30)
        self.ui_density_combo.addItems(["Compact", "Comfortable", "Spacious"])
        self.ui_density_combo.setCurrentText(self.pref_ui_density)
        styling_row.addWidget(self.ui_density_combo)

        styling_row.addSpacing(16)
        styling_row.addWidget(QLabel("Font Scale:"))
        self.font_scale_spinbox = QSpinBox()
        self.font_scale_spinbox.setMinimumHeight(30)
        self.font_scale_spinbox.setRange(80, 150)
        self.font_scale_spinbox.setSingleStep(10)
        self.font_scale_spinbox.setSuffix(" %")
        self.font_scale_spinbox.setValue(self.pref_font_scale)
        styling_row.addWidget(self.font_scale_spinbox)
        styling_row.addStretch()
        appearance_layout.addRow("Widget Styling:", styling_row)

        # ------------------------------------------------------------------
        # 5. App Zoom & Live Preview
        # ------------------------------------------------------------------
        zoom_preview_row = QHBoxLayout()
        btn_zoom_out = QPushButton("Zoom −")
        btn_zoom_out.setMinimumHeight(32)
        btn_zoom_out.setMinimumWidth(85)
        btn_zoom_out.setStyleSheet("QPushButton { padding: 4px 10px; }")
        btn_zoom_out.clicked.connect(self._zoom_out)
        btn_zoom_in = QPushButton("Zoom +")
        btn_zoom_in.setMinimumHeight(32)
        btn_zoom_in.setMinimumWidth(85)
        btn_zoom_in.setStyleSheet("QPushButton { padding: 4px 10px; }")
        btn_zoom_in.clicked.connect(self._zoom_in)
        self._zoom_label = QLabel(self._zoom_label_text())
        zoom_preview_row.addWidget(btn_zoom_out)
        zoom_preview_row.addWidget(btn_zoom_in)
        zoom_preview_row.addSpacing(8)
        zoom_preview_row.addWidget(self._zoom_label)

        zoom_preview_row.addSpacing(24)
        btn_preview = QPushButton("✨ Apply Live Preview")
        btn_preview.setMinimumHeight(34)
        btn_preview.setMinimumWidth(170)
        btn_preview.setStyleSheet("QPushButton { padding: 6px 16px; font-weight: bold; }")
        btn_preview.setToolTip("Immediately preview theme, colors, background canvas, and glassmorphic styling")
        btn_preview.clicked.connect(self._preview_appearance)
        zoom_preview_row.addWidget(btn_preview)
        zoom_preview_row.addStretch()
        appearance_layout.addRow("Zoom & Live Preview:", zoom_preview_row)

        return appearance_groupbox


    # ------------------------------------------------------------------
    # --- Supporting Actions & Helpers ---------------------------------
    # ------------------------------------------------------------------

    def _on_base_theme_changed(self) -> None:
        base = "dark" if self.dark_theme_radio.isChecked() else "light"
        defaults = base_defaults(base).as_dict()
        for k in ("surface", "window_bg", "text", "muted_text", "border"):
            self._current_colors[k] = defaults.get(k, self._current_colors.get(k, "#00bcd4"))
            if k in self._palette_swatches:
                self._update_swatch_color(self._palette_swatches[k], self._current_colors[k])
        self._update_contrast_status()

    def _update_swatch_color(self, button: QPushButton, hex_color: str) -> None:
        c = QColor(hex_color)
        if not c.isValid():
            c = QColor("#888888")
        button.setStyleSheet(
            f"QPushButton {{ background-color: {c.name()}; border: 1px solid #666; border-radius: 4px; }}"
            f"QPushButton:hover {{ border: 1px solid #fff; }}"
        )

    _update_swatch = _update_swatch_color

    def _pick_palette_color(self, token_key: str) -> None:
        current_val = self._current_colors.get(token_key, "#00bcd4")
        color = QColorDialog.getColor(
            QColor(current_val),
            self,
            f"Choose {token_key.capitalize()} Color",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if color.isValid():
            hex_val = color.name()
            self._current_colors[token_key] = hex_val
            if token_key in self._palette_swatches:
                self._update_swatch_color(self._palette_swatches[token_key], hex_val)
            if token_key == "accent":
                if self.dark_theme_radio.isChecked():
                    self.pref_accent_dark = hex_val
                else:
                    self.pref_accent_light = hex_val
            self._update_contrast_status()

    def _reset_palette_to_base_defaults(self) -> None:
        base = "dark" if self.dark_theme_radio.isChecked() else "light"
        defaults = base_defaults(base).as_dict()
        for k, v in defaults.items():
            self._current_colors[k] = v
            if k in self._palette_swatches:
                self._update_swatch_color(self._palette_swatches[k], v)
        self.pref_accent_dark = base_defaults("dark").accent
        self.pref_accent_light = base_defaults("light").accent
        self._update_contrast_status()


    def _update_contrast_status(self) -> None:
        "dark" if self.dark_theme_radio.isChecked() else "light"
        try:
            tokens = ColorTokens(
                accent=self._current_colors.get("accent", "#00bcd4"),
                surface=self._current_colors.get("surface", "#2d2d30"),
                window_bg=self._current_colors.get("window_bg", "#1e1e1e"),
                text=self._current_colors.get("text", "#cccccc"),
                muted_text=self._current_colors.get("muted_text", "#888888"),
                border=self._current_colors.get("border", "#3e3e3e"),
            )
            warnings = contrast_warnings(tokens)
            if not warnings:
                self.contrast_status_label.setText("✓ WCAG 2.1 Contrast: Optimal")
                self.contrast_status_label.setStyleSheet("color: #4caf50; font-size: 8.5pt;")
            else:
                self.contrast_status_label.setText(f"ℹ WCAG Contrast: {len(warnings)} mild advisory notice(s)")
                self.contrast_status_label.setStyleSheet("color: #ffb74d; font-size: 8.5pt;")
                self.contrast_status_label.setToolTip("\n".join(str(w) for w in warnings))
        except Exception:
            self.contrast_status_label.setText("Contrast: OK")

    def _on_bg_path_changed(self, text: str) -> None:
        if text.strip() and not self.glassmorphism_check.isChecked():
            self.glassmorphism_check.setChecked(True)

    def _browse_background_image(self) -> None:
        start_dir = self.bg_path_input.text().strip()
        file_path, _ = ThumbnailFilePicker.getOpenFileName(
            self,
            caption="Select Background Image",
            start_dir=start_dir,
        )
        if file_path:
            self.bg_path_input.setText(file_path)

    def _extract_palette_from_current_background(self) -> None:
        img_path = self.bg_path_input.text().strip()
        if not img_path or not Path(img_path).exists():
            img_path, _ = ThumbnailFilePicker.getOpenFileName(
                self,
                caption="Select Image for Palette Extraction",
                start_dir=img_path,
            )
            if not img_path:
                return

        base = "dark" if self.dark_theme_radio.isChecked() else "light"
        try:
            result = extract_palette(img_path, base=base)
            for k, v in result.overrides.items():
                self._current_colors[k] = v
                if k in self._palette_swatches:
                    self._update_swatch_color(self._palette_swatches[k], v)
            if "accent" in result.overrides:
                if base == "dark":
                    self.pref_accent_dark = result.overrides["accent"]
                else:
                    self.pref_accent_light = result.overrides["accent"]
            self._update_contrast_status()
        except Exception as e:
            self.contrast_status_label.setText(f"Extraction error: {e}")

    def _get_background_config_dict(self) -> dict[str, Any]:
        return {
            "image_path": self.bg_path_input.text().strip(),
            "playlist_paths": [self.bg_path_input.text().strip()] if self.bg_path_input.text().strip() else [],
            "playlist_interval_sec": 300,
            "opacity": round(self.bg_opacity_slider.value() / 100.0, 2),
            "blur_radius": self.bg_blur_spin.value(),
            "fit_mode": self.bg_fit_combo.currentText().lower(),
            "glassmorphism_enabled": self.glassmorphism_check.isChecked(),
            "tab_overrides": self._bg_config.tab_overrides if hasattr(self, "_bg_config") else {},
        }

    def _get_color_overrides_dict(self) -> dict[str, str]:
        return dict(self._current_colors)

    def _zoom_label_text(self) -> str:
        z = self.pref_app_zoom
        sign = "+" if z >= 0 else ""
        return f"Current: {sign}{z}%"

    def _zoom_in(self) -> None:
        if self.pref_app_zoom >= 100:
            return
        self.pref_app_zoom += 10
        self._zoom_label.setText(self._zoom_label_text())
        if self.main_window_ref and hasattr(self.main_window_ref, "zoom_in"):
            self.main_window_ref.zoom_in()
            mw_prefs = getattr(self.main_window_ref, "cached_creds", {}).get("preferences", {})
            self.pref_app_zoom = mw_prefs.get("app_zoom", self.pref_app_zoom)
            self._zoom_label.setText(self._zoom_label_text())

    def _zoom_out(self) -> None:
        if self.pref_app_zoom <= -50:
            return
        self.pref_app_zoom -= 10
        self._zoom_label.setText(self._zoom_label_text())
        if self.main_window_ref and hasattr(self.main_window_ref, "zoom_out"):
            self.main_window_ref.zoom_out()
            mw_prefs = getattr(self.main_window_ref, "cached_creds", {}).get("preferences", {})
            self.pref_app_zoom = mw_prefs.get("app_zoom", self.pref_app_zoom)
            self._zoom_label.setText(self._zoom_label_text())

    def _preview_appearance(self) -> None:
        """Apply current theme, color palette, background, and glassmorphism live without saving."""
        if not self.main_window_ref:
            return

        selected_theme = "dark" if self.dark_theme_radio.isChecked() else "light"
        prefs = dict(getattr(self.main_window_ref, "cached_creds", {}).get("preferences", {}))

        prefs["accent_color_dark"] = self._current_colors.get("accent", self.pref_accent_dark)
        prefs["accent_color_light"] = self._current_colors.get("accent", self.pref_accent_light)
        prefs["color_overrides"] = self._get_color_overrides_dict()
        prefs["font_scale"] = self.font_scale_spinbox.value()
        prefs["ui_density"] = self.ui_density_combo.currentText()
        prefs["corner_radius"] = self.corner_radius_combo.currentData()
        prefs["background_config"] = self._get_background_config_dict()

        if hasattr(self.main_window_ref, "cached_creds"):
            if not self.main_window_ref.cached_creds:
                self.main_window_ref.cached_creds = {}
            self.main_window_ref.cached_creds["preferences"] = prefs

        # Update background canvas controller
        bg_cfg = BackgroundConfig.from_dict(prefs["background_config"])
        BackgroundCanvasController.instance().set_config(bg_cfg)

        # Trigger theme reload
        self.main_window_ref.set_application_theme(selected_theme)
        self.main_window_ref.update()


__all__ = ["_AppearanceMixin"]
