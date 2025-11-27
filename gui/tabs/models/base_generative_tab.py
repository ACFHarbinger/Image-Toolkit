from PySide6.QtWidgets import QWidget, QFormLayout, QLabel


class BaseGenerativeTab(QWidget):
    """Base class for all Generative Model parameter tabs"""
    def __init__(self):
        super().__init__()
        self.params = {}
        self.widgets = {}
        
    def add_param_widget(self, layout: QFormLayout, label: str, widget: QWidget, param_name: str):
        """Helper to add a parameter widget to layout"""
        layout.addRow(QLabel(label), widget)
        self.widgets[param_name] = widget
        
    def get_params(self):
        """Override in subclasses to return parameters"""
        # A simple default implementation
        params = {}
        for key, widget in self.widgets.items():
            if hasattr(widget, 'value'):
                params[key] = widget.value()
            elif hasattr(widget, 'text'):
                params[key] = widget.text()
            elif hasattr(widget, 'isChecked'):
                params[key] = widget.isChecked()
        return params
