from PySide6.QtWidgets import (
    QVBoxLayout, QComboBox, QStackedWidget, 
    QLabel, QFormLayout
)
from .base_generative_tab import BaseGenerativeTab
from .train import R3GANTrainTab, AnythingTrainTab


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
        self.model_selector.addItem("Anything V5 (Diffusers LoRA)", "anything")
        if R3GANTrainTab:
            self.model_selector.addItem("R3GAN (NVLabs)", "r3gan")
        
        selector_layout = QFormLayout()
        selector_layout.addRow(QLabel("<b>Model Architecture:</b>"), self.model_selector)
        main_layout.addLayout(selector_layout)

        # 2. Stacked Widget (The container for the changing tabs)
        self.stack = QStackedWidget()
        
        # Initialize sub-tabs
        self.anything_tab = AnythingTrainTab()
        self.stack.addWidget(self.anything_tab)
        
        if R3GANTrainTab:
            self.r3gan_tab = R3GANTrainTab()
            self.stack.addWidget(self.r3gan_tab)

        main_layout.addWidget(self.stack)
        
        # Connect signal
        self.model_selector.currentIndexChanged.connect(self.stack.setCurrentIndex)
        
        self.setLayout(main_layout)

    def get_params(self):
        """
        Returns a dict containing the selected model type and the specific params
        of the active tab.
        """
        model_type = self.model_selector.currentData()
        
        # Get params from the currently visible widget
        active_widget = self.stack.currentWidget()
        specific_params = active_widget.get_params() if hasattr(active_widget, 'get_params') else {}
        
        return {
            "model_type": model_type,
            **specific_params
        }
