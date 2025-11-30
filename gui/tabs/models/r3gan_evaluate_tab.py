from PySide6.QtWidgets import (
    QFormLayout, QLabel, 
    QLineEdit, QCheckBox
)
from .base_generative_tab import BaseGenerativeTab


class R3GANEvaluateTab(BaseGenerativeTab):
    """Tab for evaluating a trained R3GAN model."""
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        self.add_param_widget(layout, "Model to Evaluate (.pkl):", QLineEdit(), "network")
        self.add_param_widget(layout, "Reference Dataset:", QLineEdit(), "dataset_path")
        
        layout.addRow(QLabel("Metrics to calculate:"))
        self.add_param_widget(layout, "FID (fid50k_full):", QCheckBox(), "metric_fid")
        self.add_param_widget(layout, "KID (kid50k_full):", QCheckBox(), "metric_kid")
        self.add_param_widget(layout, "Precision/Recall (pr50k3_full):", QCheckBox(), "metric_pr")
        self.add_param_widget(layout, "Inception Score (is50k):", QCheckBox(), "metric_is")
        
        self.setLayout(layout)