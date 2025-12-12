import pytest
from PySide6.QtWidgets import QWidget, QFormLayout, QComboBox, QCheckBox, QSpinBox, QLineEdit
from gui.src.classes.base_generative_tab import BaseGenerativeTab

@pytest.fixture
def gen_tab(q_app):
    tab = BaseGenerativeTab()
    layout = QFormLayout()
    tab.setLayout(layout)
    return tab

def test_add_param_widget(gen_tab):
    layout = gen_tab.layout()
    widget = QLineEdit()
    gen_tab.add_param_widget(layout, "Label", widget, "test_param")
    
    assert "test_param" in gen_tab.widgets
    assert gen_tab.widgets["test_param"] == widget
    assert layout.rowCount() > 0

def test_collect_values(gen_tab):
    layout = gen_tab.layout()
    
    # Setup widgets
    combo = QComboBox()
    combo.addItems(["A", "B"])
    gen_tab.add_param_widget(layout, "Combo", combo, "p_combo")
    
    check = QCheckBox()
    check.setChecked(True)
    gen_tab.add_param_widget(layout, "Check", check, "p_check")
    
    spin = QSpinBox()
    spin.setValue(42)
    gen_tab.add_param_widget(layout, "Spin", spin, "p_spin")
    
    line = QLineEdit()
    line.setText("Hello")
    gen_tab.add_param_widget(layout, "Line", line, "p_line")
    
    # Collect
    params = gen_tab.collect()
    
    assert params["p_combo"] == "A"
    assert params["p_check"] is True
    assert params["p_spin"] == 42
    assert params["p_line"] == "Hello"

def test_set_config(gen_tab):
    layout = gen_tab.layout()
    
    spin = QSpinBox()
    spin.setRange(0, 1000)
    gen_tab.add_param_widget(layout, "Spin", spin, "p_spin")
    
    line = QLineEdit()
    gen_tab.add_param_widget(layout, "Line", line, "p_line")
    
    config = {
        "p_spin": 100,
        "p_line": "New Value",
        "unknown_param": "ignore me"
    }
    
    gen_tab.set_config(config)
    
    assert spin.value() == 100
    assert line.text() == "New Value"
