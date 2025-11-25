from PySide6.QtWidgets import QFormLayout, QSpinBox, QLineEdit
from ..base_generative_tab import BaseGenerativeTab


class R3GANGenerateTab(BaseGenerativeTab):
    """Tab for generating images with a pre-trained R3GAN model."""
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QFormLayout()
        self.add_param_widget(layout, "Network (.pkl):", QLineEdit(), "network")
        self.add_param_widget(layout, "Output Directory:", QLineEdit(), "outdir")
        self.add_param_widget(layout, "Seeds (e.g., 0-7):", QLineEdit("0-7"), "seeds")
        self.add_param_widget(layout, "Class Index (opt.):", QSpinBox(minimum=-1, value=-1), "class_idx")
        self.setLayout(layout)
