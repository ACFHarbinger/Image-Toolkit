"""Theme Studio panel (#438): edit a ThemePack with live preview.

Standalone QWidget -- no dependency on the settings window or the main
window. Consumes the #437 schema (ThemePack / resolve / validate) and
produces a ThemePack that callers apply via gui.src.styles' existing
QSS machinery (load_qss_with_overrides + to_qss_vars bridge).

Transactional preview (opencode's round-2 answer): every edit rebuilds a
candidate ThemePack and applies it through an injected apply callback;
if the candidate fails schema validation the panel rolls back to the
last valid snapshot and reports the error -- the UI is never left in a
broken state.
"""

from __future__ import annotations

import logging
from typing import Callable

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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.src.theming.resolve import base_defaults, resolve_colors
from gui.src.theming.schema import (
    COLOR_TOKEN_KEYS,
    VALID_BASES,
    VALID_DENSITY_MODES,
    ColorTokens,
    CornerTokens,
    DensityTokens,
    ShadowTokens,
    ThemePack,
    ThemeSchemaError,
    TypographyTokens,
)
from gui.src.theming.validate import contrast_warnings

log = logging.getLogger(__name__)

#: 5 UI-facing slots -> stored token key. Text/muted are one slot per the
#: roadmap but two stored values (schema docstring).
SLOT_TO_KEY = [
    ("Primary Accent", "accent"),
    ("Surface / Card", "surface"),
    ("Window Background", "window_bg"),
    ("Text / Muted Text", "text"),
    ("Borders / Dividers", "border"),
]

#: Corner presets from gui_ux.md §2.34 Option A.
CORNER_PRESETS = [("Sharp", 0), ("Subtle", 4), ("Rounded", 8), ("Pill", 16)]


class ThemeStudioPanel(QWidget):
    """Edits one ThemePack (base + overrides + typography/corners/density)
    with live transactional preview."""

    def __init__(
        self,
        pack: ThemePack,
        apply_callback: Callable[[ThemePack], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._apply = apply_callback
        self._valid_snapshot: ThemePack = pack
        self._pack = pack
        self._swatches: dict[str, QPushButton] = {}
        self._loading = True  # suppress transactional apply during initial load
        self._build_ui()
        self._load_from_pack(pack)
        self._loading = False

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # Base theme
        base_group = QGroupBox("Base Theme")
        base_layout = QHBoxLayout(base_group)
        self._base_radios: dict[str, QRadioButton] = {}
        for base in VALID_BASES:
            rb = QRadioButton(base.capitalize())
            rb.toggled.connect(self._on_edit)
            self._base_radios[base] = rb
            base_layout.addWidget(rb)
        root.addWidget(base_group)

        # Semantic palette (5 slots)
        palette_group = QGroupBox("Semantic Palette")
        palette_layout = QFormLayout(palette_group)
        for label, key in SLOT_TO_KEY:
            row = QHBoxLayout()
            swatch = QPushButton()
            swatch.setFixedSize(180, 22)
            swatch.clicked.connect(lambda _=False, k=key: self._pick_color(k))
            self._swatches[key] = swatch
            reset_btn = QPushButton("Reset")
            reset_btn.setFixedWidth(70)
            reset_btn.clicked.connect(lambda _=False, k=key: self._reset_color(k))
            row.addWidget(swatch)
            row.addWidget(reset_btn)
            row.addStretch()
            palette_layout.addRow(f"{label}:", row)
        root.addWidget(palette_group)

        # WCAG contrast meter (advisory only)
        self.contrast_label = QLabel("")
        self.contrast_label.setWordWrap(True)
        self.contrast_label.setStyleSheet("color: #d99; padding: 4px;")
        root.addWidget(self.contrast_label)

        # Corners
        corner_group = QGroupBox("Corner Radius")
        corner_layout = QHBoxLayout(corner_group)
        self._corner_radios: list[tuple[QRadioButton, int]] = []
        for name, px in CORNER_PRESETS:
            rb = QRadioButton(f"{name} ({px}px)")
            rb.toggled.connect(self._on_edit)
            self._corner_radios.append((rb, px))
            corner_layout.addWidget(rb)
        root.addWidget(corner_group)

        # Typography
        type_group = QGroupBox("Typography")
        type_layout = QFormLayout(type_group)
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Segoe UI", "Arial", "Helvetica", "Consolas", "Georgia", "System Default"])
        self.font_combo.currentTextChanged.connect(lambda _t: self._on_edit())
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(80, 150)
        self.scale_spin.setSuffix(" %")
        self.scale_spin.valueChanged.connect(lambda _v: self._on_edit())
        self.weight_combo = QComboBox()
        self.weight_combo.addItems(["normal", "medium", "bold"])
        self.weight_combo.currentTextChanged.connect(lambda _t: self._on_edit())
        type_layout.addRow("Font family:", self.font_combo)
        type_layout.addRow("Scale:", self.scale_spin)
        type_layout.addRow("Weight:", self.weight_combo)
        root.addWidget(type_group)

        # Density + shadow
        misc_group = QGroupBox("Density & Elevation")
        misc_layout = QFormLayout(misc_group)
        self.density_combo = QComboBox()
        self.density_combo.addItems(list(VALID_DENSITY_MODES))
        self.density_combo.currentTextChanged.connect(lambda _t: self._on_edit())
        self.shadow_spin = QSpinBox()
        self.shadow_spin.setRange(0, 30)
        self.shadow_spin.setSuffix(" px")
        self.shadow_spin.valueChanged.connect(lambda _v: self._on_edit())
        misc_layout.addRow("Density:", self.density_combo)
        misc_layout.addRow("Shadow blur:", self.shadow_spin)
        root.addWidget(misc_group)

        root.addStretch()

    # ------------------------------------------------------------------
    # Load / build
    # ------------------------------------------------------------------

    def _load_from_pack(self, pack: ThemePack) -> None:
        resolved = resolve_colors(pack)
        for key, swatch in self._swatches.items():
            self._update_swatch(swatch, getattr(resolved, key))
        self._base_radios[pack.base].setChecked(True)
        for rb, px in self._corner_radios:
            rb.setChecked(pack.corners.radius_px == px)
        self.font_combo.setCurrentText(pack.typography.font_family or "System Default")
        self.scale_spin.setValue(pack.typography.scale_percent)
        self.weight_combo.setCurrentText(pack.typography.weight)
        self.density_combo.setCurrentText(pack.density.mode)
        self.shadow_spin.setValue(pack.shadows.blur_radius_px)
        self._refresh_contrast()

    def _build_candidate(self) -> ThemePack:
        base = next(b for b, rb in self._base_radios.items() if rb.isChecked())
        overrides: dict[str, str] = {}
        resolved = resolve_colors(self._pack if self._pack.base == base else ThemePack(name=self._pack.name, base=base))
        for key, swatch in self._swatches.items():
            hex_val = swatch.text().strip().upper()
            if hex_val and hex_val != getattr(resolved, key).upper():
                overrides[key] = hex_val.lower()
        font = self.font_combo.currentText()
        family = None if font == "System Default" else font
        corners = next(px for rb, px in self._corner_radios if rb.isChecked())
        return ThemePack(
            name=self._pack.name,
            base=base,
            color_overrides=overrides,
            typography=TypographyTokens(
                font_family=family,
                scale_percent=self.scale_spin.value(),
                weight=self.weight_combo.currentText(),
            ),
            corners=CornerTokens(radius_px=corners),
            shadows=ShadowTokens(blur_radius_px=self.shadow_spin.value()),
            density=DensityTokens(mode=self.density_combo.currentText()),
            backgrounds=self._pack.backgrounds,
            derive_accent_from_background=self._pack.derive_accent_from_background,
            raw_qss=self._pack.raw_qss,
        )

    # ------------------------------------------------------------------
    # Edit handling (transactional)
    # ------------------------------------------------------------------

    def _on_edit(self, *_args) -> None:
        if getattr(self, "_loading", False):
            return
        try:
            candidate = self._build_candidate()
        except ThemeSchemaError as exc:
            self._rollback(str(exc))
            return
        self._valid_snapshot = candidate
        self._pack = candidate
        self._refresh_contrast()
        self._apply(candidate)

    def _rollback(self, reason: str) -> None:
        """Restore the last valid snapshot and re-apply it."""
        log.warning("Theme Studio rollback: %s", reason)
        self._load_from_pack(self._valid_snapshot)
        self._apply(self._valid_snapshot)
        self.contrast_label.setText(f"Reverted invalid edit: {reason}")

    def _pick_color(self, key: str) -> None:
        current = self._swatches[key].text().strip() or "#888888"
        color = QColorDialog.getColor(QColor(current), self, f"Choose {key}")
        if color.isValid():
            self._update_swatch(self._swatches[key], color.name())
            self._on_edit()

    def _reset_color(self, key: str) -> None:
        base = next(b for b, rb in self._base_radios.items() if rb.isChecked())
        default = getattr(base_defaults(base), key)
        self._update_swatch(self._swatches[key], default)
        self._on_edit()

    def _update_swatch(self, button: QPushButton, hex_color: str) -> None:
        c = QColor(hex_color)
        if not c.isValid():
            c = QColor("#888888")
        lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255.0
        text_color = "black" if lum > 0.5 else "white"
        button.setStyleSheet(
            f"QPushButton {{ background-color: {c.name()}; border: 1px solid #888; border-radius: 3px; color: {text_color}; font-weight: bold; }}"
        )
        button.setText(c.name())

    def _refresh_contrast(self) -> None:
        try:
            resolved = resolve_colors(self._build_candidate())
        except ThemeSchemaError:
            resolved = resolve_colors(self._valid_snapshot)
        warnings = contrast_warnings(resolved)
        if not warnings:
            self.contrast_label.setText("WCAG 2.1 AA: all token pairs pass (advisory).")
            self.contrast_label.setStyleSheet("color: #8d8; padding: 4px;")
        else:
            msgs = "\n".join(w.message for w in warnings)
            self.contrast_label.setText(f"WCAG 2.1 AA (advisory, not enforced):\n{msgs}")
            self.contrast_label.setStyleSheet("color: #d99; padding: 4px;")

    @property
    def pack(self) -> ThemePack:
        return self._pack


__all__ = ["SLOT_TO_KEY", "CORNER_PRESETS", "ThemeStudioPanel"]
