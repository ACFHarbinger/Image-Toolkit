from PySide6.QtWidgets import (
    QFormLayout, QLabel, QLineEdit,
    QComboBox, QTextEdit, QVBoxLayout
)
from .base_generative_tab import BaseGenerativeTab


class MetaCLIPInferenceTab(BaseGenerativeTab):
    """Tab for Meta CLIP Zero-Shot Classification."""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        
        models = [
            "Meta CLIP 2 (ViT-H-14, Worldwide)", 
            "Meta CLIP 2 (ViT-bigG-14, Worldwide)",
            "Meta CLIP 1 (ViT-G-14, 2.5B)",
            "Meta CLIP 1 (ViT-H-14, 2.5B)"
        ]
        self.add_param_widget(layout, "Model Version:", QComboBox(), "model_version")
        self.widgets["model_version"].addItems(models)

        self.add_param_widget(layout, "Image Path:", QLineEdit(), "image_path")
        
        prompts_layout = QVBoxLayout()
        prompts_label = QLabel("Text Prompts (one per line):")
        self.widgets["text_prompts"] = QTextEdit("a diagram\na dog\na cat")
        prompts_layout.addWidget(prompts_label)
        prompts_layout.addWidget(self.widgets["text_prompts"])
        
        layout.addRow(prompts_layout)
        self.setLayout(layout)

    def get_params(self):
        # Override Base.get_params to format for worker
        params = self.collect()
        if "text_prompts" in params:
            # Worker expects list of strings, UI returns single string
            params["text_prompts"] = params["text_prompts"].splitlines()
        return params
        
    # collect/set_config are handled by BaseGenerativeTab for QTextEdit strings