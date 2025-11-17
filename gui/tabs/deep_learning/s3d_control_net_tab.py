from PySide6.QtWidgets import (
    QComboBox, QSpinBox,
    QFormLayout, QLineEdit,
)
from .base_generative_tab import BaseGenerativeTab


class SD3ControlNetTab(BaseGenerativeTab):
    """Tab for SD 3.5 ControlNet generation."""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()

        # Base Model
        base_models = [
            "models/sd3.5_large.safetensors",
            "models/sd3.5_large_turbo.safetensors",
        ]
        self.add_param_widget(layout, "Base Model:", QComboBox(), "model")
        self.widgets["model"].addItems(base_models)
        self.widgets["model"].setEditable(True)

        # ControlNet Model
        cn_models = [
            "models/sd3.5_large_controlnet_blur.safetensors",
            "models/sd3.5_large_controlnet_canny.safetensors",
            "models/sd3.5_large_controlnet_depth.safetensors",
        ]
        self.add_param_widget(layout, "ControlNet Model:", QComboBox(), "controlnet_ckpt")
        self.widgets["controlnet_ckpt"].addItems(cn_models)
        self.widgets["controlnet_ckpt"].setEditable(True)

        self.add_param_widget(layout, "ControlNet Cond. Image:", QLineEdit("inputs/canny.png"), "controlnet_cond_image")
        self.add_param_widget(layout, "Prompt:", QLineEdit("A Night time photo..."), "prompt")
        self.add_param_widget(layout, "Width:", QSpinBox(minimum=256, maximum=4096, value=1024), "width")
        self.add_param_widget(layout, "Height:", QSpinBox(minimum=256, maximum=4096, value=1024), "height")

        self.setLayout(layout)
