from PySide6.QtWidgets import (
    QFormLayout, QLineEdit,
    QComboBox, QSpinBox, QCheckBox
)
from .base_generative_tab import BaseGenerativeTab


class SD3TextToImageTab(BaseGenerativeTab):
    """Tab for standard SD 3.5 Text-to-Image generation."""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        
        models = [
            "models/sd3.5_large.safetensors",
            "models/sd3.5_large_turbo.safetensors",
            "models/sd3.5_medium.safetensors",
            "models/sd3_medium.safetensors"
        ]
        self.add_param_widget(layout, "Model:", QComboBox(), "model")
        self.widgets["model"].addItems(models)
        self.widgets["model"].setEditable(True)

        self.add_param_widget(layout, "Prompt:", QLineEdit("cute wallpaper art of a cat"), "prompt")
        self.add_param_widget(layout, "Output Postfix (opt.):", QLineEdit(), "postfix")
        
        self.add_param_widget(layout, "Width:", QSpinBox(minimum=256, maximum=4096, value=1024), "width")
        self.add_param_widget(layout, "Height:", QSpinBox(minimum=256, maximum=4096, value=1024), "height")
        self.add_param_widget(layout, "Steps:", QSpinBox(minimum=1, maximum=200, value=28), "steps")

        self.add_param_widget(layout, "Skip Layer Cfg (SD3.5-M):", QCheckBox(), "skip_layer_cfg")
        
        self.setLayout(layout)
