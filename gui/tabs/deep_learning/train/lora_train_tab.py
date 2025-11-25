from PySide6.QtWidgets import (
    QFormLayout, QLineEdit, QMessageBox,
    QSpinBox, QDoubleSpinBox, QPushButton
)
from ..base_generative_tab import BaseGenerativeTab
from backend.src.models.lora_tuner import LoRATuner


class AnythingTrainTab(BaseGenerativeTab):
    """
    The specific training tab for Anything V5 (Diffusers/LoRA).
    """
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        
        # Paths
        self.add_param_widget(layout, "Training Data Directory:", QLineEdit("./my_training_images"), "data_dir")
        self.add_param_widget(layout, "Output Directory:", QLineEdit("output_lora"), "output_dir")
        self.add_param_widget(layout, "Base Model ID:", QLineEdit("stablediffusionapi/anything-v5"), "model_id")
        
        # LoRA Configuration
        self.add_param_widget(layout, "LoRA Rank:", QSpinBox(minimum=1, value=4, maximum=128), "rank")
        self.add_param_widget(layout, "LoRA Alpha:", QSpinBox(minimum=1, value=32, maximum=128), "alpha")
        
        # Training Hyperparameters
        self.add_param_widget(layout, "Trigger Word (Prompt):", QLineEdit("1girl, style of my_character"), "instance_prompt")
        self.add_param_widget(layout, "Epochs:", QSpinBox(minimum=1, value=50, maximum=1000), "epochs")
        self.add_param_widget(layout, "Batch Size:", QSpinBox(minimum=1, value=1, maximum=16), "batch_size")
        
        # Learning Rate
        lr_box = QDoubleSpinBox()
        lr_box.setDecimals(5)
        lr_box.setRange(0.00001, 0.01)
        lr_box.setValue(0.0001)
        lr_box.setSingleStep(0.00005)
        self.add_param_widget(layout, "Learning Rate:", lr_box, "learning_rate")

        # Action Button
        self.train_btn = QPushButton("Start LoRA Training")
        self.train_btn.clicked.connect(self.start_training)
        layout.addRow(self.train_btn)

        self.setLayout(layout)

    def start_training(self):
        if LoRATuner is None:
            QMessageBox.critical(self, "Error", "fine_tune_anime.py not found.")
            return

        params = self.get_params()
        
        try:
            # 1. Initialize Tuner
            tuner = LoRATuner(
                model_id=params["model_id"], 
                output_dir=params["output_dir"]
            )
            
            # 2. Configure
            tuner.configure_lora(
                rank=params["rank"], 
                alpha=params["alpha"]
            )
            
            # 3. Train
            # Note: This will block the UI in this simple implementation. 
            # For production, use QThread.
            tuner.train(
                data_dir=params["data_dir"],
                instance_prompt=params["instance_prompt"],
                epochs=params["epochs"],
                batch_size=params["batch_size"],
                learning_rate=params["learning_rate"]
            )
            
            QMessageBox.information(self, "Success", f"Training complete! LoRA saved to {params['output_dir']}")
            
        except Exception as e:
            QMessageBox.critical(self, "Training Error", str(e))