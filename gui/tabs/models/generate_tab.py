from PySide6.QtWidgets import (
    QVBoxLayout, QComboBox, QStackedWidget, 
    QLabel, QFormLayout
)
from .base_generative_tab import BaseGenerativeTab
from .gen import R3GANGenerateTab, LoRAGenerateTab, SD3GenerateTab


class UnifiedGenerateTab(BaseGenerativeTab):
    """
    Master tab that allows selecting the Model Architecture (Anything V5 vs R3GAN vs SD3)
    for image generation.
    """
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # 1. Model Selector
        self.model_selector = QComboBox()
        self.model_selector.addItem("LoRA (Diffusion and GANs)", "anything")
        self.model_selector.addItem("Stable Diffusion 3.5", "sd3")
        if R3GANGenerateTab:
            self.model_selector.addItem("R3GAN (NVLabs)", "r3gan")
        
        selector_layout = QFormLayout()
        selector_layout.addRow(QLabel("<b>Model Architecture:</b>"), self.model_selector)
        main_layout.addLayout(selector_layout)

        # 2. Stacked Widget
        self.stack = QStackedWidget()
        
        self.anything_tab = LoRAGenerateTab()
        self.stack.addWidget(self.anything_tab)
        
        self.sd3_tab = SD3GenerateTab()
        self.stack.addWidget(self.sd3_tab)
        
        if R3GANGenerateTab:
            self.r3gan_tab = R3GANGenerateTab()
            self.stack.addWidget(self.r3gan_tab)

        main_layout.addWidget(self.stack)
        
        # Connect signal
        self.model_selector.currentIndexChanged.connect(self.stack.setCurrentIndex)
        
        self.setLayout(main_layout)

    def get_params(self):
        """
        Returns a dict containing the selected model type and the specific params.
        """
        model_type = self.model_selector.currentData()
        
        active_widget = self.stack.currentWidget()
        specific_params = active_widget.get_params() if hasattr(active_widget, 'get_params') else {}
        
        return {
            "model_type": model_type,
            **specific_params
        }
