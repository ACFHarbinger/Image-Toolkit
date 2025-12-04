from PySide6.QtWidgets import QFormLayout, QLineEdit, QComboBox, QSpinBox, QCheckBox
from ..base_generative_tab import BaseGenerativeTab


class SD3GenerateTab(BaseGenerativeTab):
    """Unified Tab for SD 3.5 Generation (Text-to-Image & ControlNet)."""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()

        # --- Base Model Section ---
        base_models = [
            "models/sd3.5_large.safetensors",
            "models/sd3.5_large_turbo.safetensors",
            "models/sd3.5_medium.safetensors",
            "models/sd3_medium.safetensors",
        ]
        self.add_param_widget(layout, "Base Model:", QComboBox(), "model")
        self.widgets["model"].addItems(base_models)
        self.widgets["model"].setEditable(True)

        self.add_param_widget(
            layout, "Prompt:", QLineEdit("cute wallpaper art of a cat"), "prompt"
        )
        self.add_param_widget(layout, "Output Postfix (opt.):", QLineEdit(), "postfix")

        # --- Dimensions & Steps ---
        self.add_param_widget(
            layout, "Width:", QSpinBox(minimum=256, maximum=4096, value=1024), "width"
        )
        self.add_param_widget(
            layout, "Height:", QSpinBox(minimum=256, maximum=4096, value=1024), "height"
        )
        self.add_param_widget(
            layout, "Steps:", QSpinBox(minimum=1, maximum=200, value=28), "steps"
        )
        self.add_param_widget(
            layout, "Skip Layer Cfg (SD3.5-M):", QCheckBox(), "skip_layer_cfg"
        )

        # --- ControlNet Section ---
        cn_models = [
            "None",
            "models/sd3.5_large_controlnet_blur.safetensors",
            "models/sd3.5_large_controlnet_canny.safetensors",
            "models/sd3.5_large_controlnet_depth.safetensors",
        ]
        self.add_param_widget(
            layout, "ControlNet Model:", QComboBox(), "controlnet_ckpt"
        )
        self.widgets["controlnet_ckpt"].addItems(cn_models)
        self.widgets["controlnet_ckpt"].setEditable(True)

        self.add_param_widget(
            layout,
            "ControlNet Cond. Image:",
            QLineEdit("inputs/canny.png"),
            "controlnet_cond_image",
        )

        self.setLayout(layout)
