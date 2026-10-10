import contextlib

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QWidget,
)

from gui.src.theming.theme_api import color

# Progressive disclosure complexity tiers (#731)
TIER_SIMPLE = "simple"
TIER_STANDARD = "standard"
TIER_ADVANCED = "advanced"
DISCLOSURE_TIERS = (TIER_SIMPLE, TIER_STANDARD, TIER_ADVANCED)

# v1 wrote QComboBox.currentText() (friendly labels) and, on the unified
# train/generate hosts, selected_model_index. v2 writes itemData and
# selected_model. set_config still accepts v1 snapshots.
CONFIG_SCHEMA_VERSION = 2
CONFIG_SCHEMA_KEY = "config_schema"
SELECTED_MODEL_KEY = "selected_model"
LEGACY_SELECTED_MODEL_INDEX_KEY = "selected_model_index"

_META_CONFIG_KEYS = frozenset({CONFIG_SCHEMA_KEY, "config_migration_note"})



def combo_persist_value(combo: QComboBox):
    """Stable field id when the combo has itemData; label otherwise."""
    data = combo.currentData()
    return combo.currentText() if data is None else data


def collect_selected_model(combo: QComboBox) -> dict:
    """Schema + architecture id for the unified train/generate hosts."""
    return {
        CONFIG_SCHEMA_KEY: CONFIG_SCHEMA_VERSION,
        SELECTED_MODEL_KEY: combo_persist_value(combo),
    }


def apply_selected_model(combo: QComboBox, config: dict) -> str | None:
    """Restore architecture by id, then by legacy combo index."""
    if SELECTED_MODEL_KEY in config:
        return apply_combo_value(combo, config[SELECTED_MODEL_KEY])
    if LEGACY_SELECTED_MODEL_INDEX_KEY not in config:
        return None
    index = config[LEGACY_SELECTED_MODEL_INDEX_KEY]
    if isinstance(index, int) and 0 <= index < combo.count():
        combo.setCurrentIndex(index)
        return None
    kept = combo.currentText() or "default"
    return f"Unknown {LEGACY_SELECTED_MODEL_INDEX_KEY} {index!r} — kept {kept!r}."


def apply_combo_value(combo: QComboBox, value) -> str | None:
    """Restore *value* by id, then by legacy label.

    Returns a one-line migration note when neither matches. The current
    index is left unchanged — a miss must not silently become index 0.
    """
    if value is None:
        return None
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)
        return None
    index = combo.findText(str(value))
    if index >= 0:
        combo.setCurrentIndex(index)
        return None
    kept = combo.currentText() or "default"
    return f"Unknown {value!r} — kept {kept!r}."


def _fold(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def model_choice_label(label: str, model_id: str) -> str:
    """Combo display text for a model choice (#728).

    Friendly labels must not conceal what they resolve to — two
    "Illustrious" entries both map to stabilityai/stable-diffusion-xl-base-1.0,
    which the label alone hides. Appends the resolved id unless the label
    already carries it (comparison folds case and punctuation).
    """
    if _fold(model_id) in _fold(label) or _fold(label) in _fold(model_id):
        return label
    return f"{label} · {model_id}"


class BaseGenerativeTab(QWidget):
    """Base class for all Generative Model parameter tabs"""

    effective_config_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.params = {}
        self.widgets = {}
        self._param_rows: dict[str, tuple[QWidget, QWidget, str]] = {}
        self._active_disclosure_tier = TIER_STANDARD
        self.config_migration_note: str | None = None
        self._migration_label: QLabel | None = None

    def add_param_widget(
        self,
        layout: QFormLayout,
        label: str,
        widget: QWidget,
        param_name: str,
        tier: str = TIER_STANDARD,
    ):
        """Helper to add a parameter widget to layout with disclosure tier support."""
        lbl = QLabel(label)
        lbl.setProperty("disclosure_tier", tier)
        widget.setProperty("disclosure_tier", tier)
        layout.addRow(lbl, widget)
        self.widgets[param_name] = widget
        self._param_rows[param_name] = (lbl, widget, tier)
        self._connect_widget_change(widget)

    def tag_field(
        self,
        widget: QWidget,
        tier: str = TIER_STANDARD,
        label: QWidget | None = None,
    ) -> None:
        """Tag an arbitrary widget or container row with a disclosure tier."""
        widget.setProperty("disclosure_tier", tier)
        if label is not None:
            label.setProperty("disclosure_tier", tier)
        self._connect_widget_change(widget)

    def _connect_widget_change(self, widget: QWidget) -> None:
        """Connect change signals to notify of effective config updates."""
        if isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(lambda _idx: self.notify_effective_config_changed())
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.valueChanged.connect(lambda _val: self.notify_effective_config_changed())
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda _txt: self.notify_effective_config_changed())
        elif isinstance(widget, QCheckBox):
            widget.toggled.connect(lambda _chk: self.notify_effective_config_changed())

    def notify_effective_config_changed(self) -> None:
        """Emit the effective configuration summary string."""
        summary = self.get_effective_config_summary()
        self.effective_config_changed.emit(summary)

    def get_effective_config_summary(self) -> str:
        """Return a read-only one-line summary of the effective configuration."""
        active_widget = getattr(getattr(self, "stack", None), "currentWidget", lambda: None)()
        if active_widget is not None and hasattr(active_widget, "get_effective_config_summary"):
            return active_widget.get_effective_config_summary()
        items: list[str] = []
        for k, w in self.widgets.items():
            if isinstance(w, QComboBox):
                items.append(f"{k}: {combo_persist_value(w)}")
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                items.append(f"{k}: {w.value()}")
            elif isinstance(w, QLineEdit):
                text = w.text().strip()
                if text:
                    items.append(f"{k}: '{text}'")
        return " · ".join(items) if items else "Default"

    def apply_disclosure_tier(self, tier: str) -> None:
        """Filter form rows based on the selected progressive disclosure tier (#731)."""
        if tier not in DISCLOSURE_TIERS:
            tier = TIER_STANDARD
        self._active_disclosure_tier = tier
        visible_tiers = {TIER_SIMPLE}
        if tier in (TIER_STANDARD, TIER_ADVANCED):
            visible_tiers.add(TIER_STANDARD)
        if tier == TIER_ADVANCED:
            visible_tiers.add(TIER_ADVANCED)

        # 1. Update registered param rows
        for lbl, widget, row_tier in self._param_rows.values():
            is_vis = row_tier in visible_tiers
            layout = self.layout()
            if isinstance(layout, QFormLayout) and hasattr(layout, "setRowVisible"):
                layout.setRowVisible(widget, is_vis)
            else:
                widget.setVisible(is_vis)
                lbl.setVisible(is_vis)

        # 2. Update any other tagged child widgets or custom containers
        for child in self.findChildren(QWidget):
            child_tier = child.property("disclosure_tier")
            if child_tier is not None:
                is_vis = child_tier in visible_tiers
                layout = self.layout()
                if isinstance(layout, QFormLayout) and hasattr(layout, "setRowVisible"):
                    layout.setRowVisible(child, is_vis)
                else:
                    child.setVisible(is_vis)

        # 3. Propagate to sub-tabs if hosted in a QStackedWidget
        stack = getattr(self, "stack", None)
        if isinstance(stack, QStackedWidget):
            for idx in range(stack.count()):
                sub = stack.widget(idx)
                if hasattr(sub, "apply_disclosure_tier"):
                    sub.apply_disclosure_tier(tier)


    def collect(self) -> dict:
        """Collects the current values from all registered widgets."""
        params = {CONFIG_SCHEMA_KEY: CONFIG_SCHEMA_VERSION}
        for key, widget in self.widgets.items():
            if isinstance(widget, QComboBox):
                params[key] = combo_persist_value(widget)
            elif isinstance(widget, QCheckBox):
                params[key] = widget.isChecked()  # pyrefly: ignore [unsupported-operation]
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                params[key] = widget.value() # pyrefly: ignore [unsupported-operation]
            elif isinstance(widget, QLineEdit):
                params[key] = widget.text()
            elif isinstance(widget, QTextEdit):
                params[key] = widget.toPlainText()
        return params

    def set_config(self, config: dict):
        """Sets the values of registered widgets from a config dictionary."""
        notes: list[str] = []
        for key, value in config.items():
            if key in _META_CONFIG_KEYS or key not in self.widgets:
                continue
            widget = self.widgets[key]
            if isinstance(widget, QComboBox):
                note = apply_combo_value(widget, value)
                if note:
                    notes.append(note)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                with contextlib.suppress(ValueError):
                    widget.setValue(value)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QTextEdit):
                widget.setPlainText(str(value))
        self.show_config_migration_note(notes)

    def show_config_migration_note(self, notes: list[str]) -> None:
        """Show or clear the one-line note for unknown combo ids."""
        text = " ".join(notes).strip()
        self.config_migration_note = text or None
        if self._migration_label is None:
            self._migration_label = QLabel()
            self._migration_label.setObjectName("config_migration_note")
            self._migration_label.setWordWrap(True)
            self._migration_label.setStyleSheet(f"color: {color('muted_text')};")
            layout = self.layout()
            if isinstance(layout, QFormLayout):
                layout.insertRow(0, self._migration_label)
            elif layout is not None and hasattr(layout, "insertWidget"):
                layout.insertWidget(0, self._migration_label)
        self._migration_label.setText(text)
        self._migration_label.setVisible(bool(text))

    def get_default_config(self) -> dict:
        """Returns the current state as the default config."""
        return self.collect()

    def get_params(self):
        """Legacy accessor for workers; wraps collect() but allows for overrides."""
        # For simple tabs, collect() returns exactly what's needed.
        # Subclasses can override this if they need to transform data (e.g. split lines).
        return self.collect()
