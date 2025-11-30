from PySide6.QtWidgets import (
    QVBoxLayout, QComboBox, QStackedWidget, 
    QLabel, QFormLayout
)
from .base_generative_tab import BaseGenerativeTab
from .train import R3GANTrainTab, LoRATrainTab


class UnifiedTrainTab(BaseGenerativeTab):
    """
    Master tab that allows selecting the Model Architecture (Anything V5 vs R3GAN)
    and switches the interface accordingly.
    """
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # 1. Model Selector
        self.model_selector = QComboBox()
        self.model_selector.addItem("LoRA (Diffusion and GANs)", "anything")
        if R3GANTrainTab:
            self.model_selector.addItem("R3GAN (NVLabs)", "r3gan")
        
        selector_layout = QFormLayout()
        selector_layout.addRow(QLabel("<b>Model Architecture:</b>"), self.model_selector)
        main_layout.addLayout(selector_layout)

        # 2. Stacked Widget (The container for the changing tabs)
        self.stack = QStackedWidget()
        
        # Initialize sub-tabs
        self.anything_tab = LoRATrainTab()
        self.stack.addWidget(self.anything_tab)
        
        if R3GANTrainTab:
            self.r3gan_tab = R3GANTrainTab()
            self.stack.addWidget(self.r3gan_tab)

        main_layout.addWidget(self.stack)
        
        # Connect signal
        self.model_selector.currentIndexChanged.connect(self.stack.setCurrentIndex)
        
        self.setLayout(main_layout)

    def collect(self) -> dict:
        active_index = self.stack.currentIndex()
        active_widget = self.stack.currentWidget()
        
        sub_config = {}
        if hasattr(active_widget, 'collect'):
            sub_config = active_widget.collect()
            
        return {
            "selected_model_index": active_index,
            "sub_config": sub_config
        }

    def set_config(self, config: dict):
        if "selected_model_index" in config:
            idx = config["selected_model_index"]
            if 0 <= idx < self.model_selector.count():
                self.model_selector.setCurrentIndex(idx)
        
        if "sub_config" in config:
            active_widget = self.stack.currentWidget()
            if hasattr(active_widget, 'set_config'):
                active_widget.set_config(config["sub_config"])

    def get_default_config(self) -> dict:
        return {
            "selected_model_index": 0,
            "sub_config": self.anything_tab.get_default_config()
        }