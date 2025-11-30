from PySide6.QtWidgets import (
    QFormLayout, QLineEdit,
    QSpinBox, QComboBox, QCheckBox
)
from ..base_generative_tab import BaseGenerativeTab
from backend.src.utils.definitions import LOCAL_SOURCE_PATH


class R3GANTrainTab(BaseGenerativeTab):
    """Tab for training a new R3GAN model."""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        self.add_param_widget(layout, "Output Directory:", QLineEdit("./training-runs"), "outdir")
        self.add_param_widget(layout, "Dataset (.zip):", QLineEdit(), LOCAL_SOURCE_PATH)
        
        presets = ["CIFAR10", "FFHQ-64", "FFHQ-256", "ImageNet-32", "ImageNet-64"]
        self.add_param_widget(layout, "Preset:", QComboBox(), "preset")
        self.widgets["preset"].addItems(presets)

        self.add_param_widget(layout, "GPUs:", QSpinBox(minimum=1, value=8), "gpus")
        self.add_param_widget(layout, "Batch Size:", QSpinBox(minimum=1, value=256, maximum=8192), "batch")
        
        self.add_param_widget(layout, "Mirror Data:", QCheckBox(), "mirror")
        self.add_param_widget(layout, "Use Augmentation:", QCheckBox(), "aug")
        self.add_param_widget(layout, "Conditional GAN:", QCheckBox(), "cond")

        self.add_param_widget(layout, "Log Frequency (ticks):", QSpinBox(minimum=1, value=1), "tick")
        self.add_param_widget(layout, "Snapshot Frequency (snaps):", QSpinBox(minimum=1, value=200), "snap")
        
        self.setLayout(layout)