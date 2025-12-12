from PySide6.QtWidgets import (
    QWidget,
    QFormLayout,
    QLabel,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QTextEdit,
)


class BaseGenerativeTab(QWidget):
    """Base class for all Generative Model parameter tabs"""

    def __init__(self):
        super().__init__()
        self.params = {}
        self.widgets = {}

    def add_param_widget(
        self, layout: QFormLayout, label: str, widget: QWidget, param_name: str
    ):
        """Helper to add a parameter widget to layout"""
        layout.addRow(QLabel(label), widget)
        self.widgets[param_name] = widget

    def collect(self) -> dict:
        """Collects the current values from all registered widgets."""
        params = {}
        for key, widget in self.widgets.items():
            if isinstance(widget, QComboBox):
                params[key] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                params[key] = widget.isChecked()
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                params[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                params[key] = widget.text()
            elif isinstance(widget, QTextEdit):
                params[key] = widget.toPlainText()
        return params

    def set_config(self, config: dict):
        """Sets the values of registered widgets from a config dictionary."""
        for key, value in config.items():
            if key in self.widgets:
                widget = self.widgets[key]
                if isinstance(widget, QComboBox):
                    # Try setting by text, fail silently if not found
                    index = widget.findText(str(value))
                    if index >= 0:
                        widget.setCurrentIndex(index)
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    try:
                        widget.setValue(float(value))
                    except:
                        pass
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, QTextEdit):
                    widget.setPlainText(str(value))

    def get_default_config(self) -> dict:
        """Returns the current state as the default config."""
        return self.collect()

    def get_params(self):
        """Legacy accessor for workers; wraps collect() but allows for overrides."""
        # For simple tabs, collect() returns exactly what's needed.
        # Subclasses can override this if they need to transform data (e.g. split lines).
        return self.collect()
