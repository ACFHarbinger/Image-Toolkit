import threading

from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtWidgets import (
    QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, 
    QPushButton, QComboBox, QLabel, QWidget,
    QHBoxLayout, QFileDialog, QMessageBox
)
from ..base_generative_tab import BaseGenerativeTab
from backend.src.models.gan_wrapper import GanWrapper
from backend.src.models.lora_diffusion import LoRATuner
from backend.src.utils.definitions import LOCAL_SOURCE_PATH


class LoRATrainTab(BaseGenerativeTab):
    # --- Define Signals for Thread-Safe Communication ---
    # Signal to update the status text (msg)
    update_status_signal = Signal(str)
    # Signal when training finishes (status_type, message)
    # status_type can be: "success", "cancel", "error"
    training_finished_signal = Signal(str, str)

    def __init__(self):
        super().__init__()
        
        # Initialize last browsed directory
        self.last_browsed_scan_dir = LOCAL_SOURCE_PATH
        
        self.init_ui()
        
        # Connect Signals to Main Thread Slots
        self.update_status_signal.connect(self.handle_status_update)
        self.training_finished_signal.connect(self.handle_training_finished)
        
    def init_ui(self):
        layout = QFormLayout()
        
        # --- Model Selection ---
        self.model_selector = QComboBox()
        models = [
            ("Anything V5", "stablediffusionapi/anything-v5"),
            ("Waifu Diffusion v1.4", "hakurei/waifu-diffusion-v1-4"),
            ("Counterfeit V3.0", "gsdf/Counterfeit-V3.0"),
            ("Animagine XL 3.1", "cagliostrolab/animagine-xl-3.1"), 
            ("Animagine XL 4.0", "cagliostrolab/animagine-xl-4.0"),
            ("AnimeGANv2", "animegan_v2"), 
        ]
        
        for name, model_id in models:
            self.model_selector.addItem(name, model_id)
            
        self.add_param_widget(layout, "Base Model:", self.model_selector, "model_id")
        self.model_selector.currentIndexChanged.connect(self.update_ui_visibility)

        # Dataset Folder
        folder_container = QWidget()
        folder_layout = QHBoxLayout(folder_container)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        
        self.data_dir_edit = QLineEdit(self.last_browsed_scan_dir)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_dataset)
        
        folder_layout.addWidget(self.data_dir_edit)
        folder_layout.addWidget(self.browse_btn)
        layout.addRow("Dataset Folder:", folder_container)

        self.add_param_widget(layout, "Output Name:", QLineEdit("my_model"), "output_name")

        # --- Dynamic Configs ---
        self.lora_group = QWidget()
        lora_layout = QFormLayout(self.lora_group)
        self.prompt_edit = QLineEdit("1girl, style of my_char")
        self.rank_box = QSpinBox()
        self.rank_box.setValue(4)
        
        lora_layout.addRow("Trigger Word (Prompt):", self.prompt_edit)
        lora_layout.addRow("LoRA Rank:", self.rank_box)
        layout.addRow(self.lora_group)

        # Common Params
        self.add_param_widget(layout, "Epochs:", QSpinBox(minimum=1, value=5, maximum=100), "epochs")
        self.add_param_widget(layout, "Batch Size:", QSpinBox(minimum=1, value=1, maximum=32), "batch_size")
        
        lr_box = QDoubleSpinBox()
        lr_box.setRange(1e-6, 1e-3)
        lr_box.setValue(1e-4)
        lr_box.setDecimals(6)
        self.add_param_widget(layout, "Learning Rate:", lr_box, "learning_rate")

        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        self.train_btn = QPushButton("Start Training")
        self.cancel_btn = QPushButton("Cancel")
        
        self.train_btn.clicked.connect(self.start_training_thread)
        self.cancel_btn.clicked.connect(self.cancel_training)
        
        button_layout.addWidget(self.train_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addRow(button_layout)
        
        self.cancel_btn.setEnabled(False) # Disabled by default
        
        self.status_label = QLabel("Ready")
        layout.addRow(self.status_label)

        self.setLayout(layout)

    def browse_dataset(self):
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select Dataset Folder",
            self.last_browsed_scan_dir
        )
        if directory:
            self.data_dir_edit.setText(directory)
            self.last_browsed_scan_dir = directory

    def update_ui_visibility(self):
        is_gan = self.model_selector.currentData() == "animegan_v2"
        self.lora_group.setVisible(not is_gan)
        self.cancel_btn.setEnabled(False) # Ensure disabled when idle

    def cancel_training(self):
        model_id = self.model_selector.currentData()
        if model_id == "animegan_v2":
            GanWrapper.cancel_process()
        else:
            LoRATuner.cancel_process()
            
        self.cancel_btn.setEnabled(False)
        self.train_btn.setEnabled(True)
        self.handle_status_update("Cancellation requested...")

    # --- Slots (Main Thread) ---
    @Slot(str)
    def handle_status_update(self, text):
        """Updates label from signal."""
        self.status_label.setText(text)
        print(f"[GUI] {text}")

    @Slot(str, str)
    def handle_training_finished(self, status_type, message):
        """Handles end of training logic on Main Thread."""
        self.train_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        # Reset flags
        LoRATuner.is_cancelled = False
        GanWrapper.is_cancelled = False
        
        if status_type == "success":
            self.status_label.setText(message)
            QMessageBox.information(self, "Success", message)
        elif status_type == "cancel":
            self.status_label.setText("Stopped.")
            QMessageBox.warning(self, "Result", message)
        else: # error
            self.status_label.setText("Error occurred.")
            QMessageBox.critical(self, "Error", message)

    def start_training_thread(self):
        self.train_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("Initializing Training...")
        
        # IMPORTANT: Read all GUI values here (Main Thread) and pass to thread.
        # Reading widgets inside the thread is unsafe.
        params = self.get_params()
        
        # Manual overrides/additions
        config = {
            "params": params,
            "data_dir": self.data_dir_edit.text(),
            "model_id": self.model_selector.currentData(),
            "rank": self.rank_box.value(),
            "prompt": self.prompt_edit.text(),
            "output_name": params.get("output_name", "output_lora") 
        }

        # Start Thread
        thread = threading.Thread(target=self.run_training, kwargs=config)
        thread.start()

    def run_training(self, params, data_dir, model_id, rank, prompt, output_name):
        """Background Worker Thread."""
        is_cancelled = False
        
        try:
            if model_id == "animegan_v2":
                self.update_status_signal.emit("Starting GAN Fine-tuning...")
                gan = GanWrapper()
                gan.train(
                    style_data_dir=data_dir,
                    epochs=params["epochs"],
                    lr=params["learning_rate"],
                    batch_size=params["batch_size"]
                )
                is_cancelled = GanWrapper.is_cancelled
            else:
                self.update_status_signal.emit(f"Loading Diffusion Model: {model_id}...")
                tuner = LoRATuner(model_id=model_id, output_dir=output_name)
                
                tuner.configure_lora(rank=rank)
                self.update_status_signal.emit("Training started...")
                tuner.train(
                    data_dir=data_dir,
                    instance_prompt=prompt,
                    epochs=params["epochs"],
                    learning_rate=params["learning_rate"],
                    batch_size=params["batch_size"]
                )
                is_cancelled = LoRATuner.is_cancelled
                
            if is_cancelled:
                self.training_finished_signal.emit("cancel", "Training process was stopped by the user.")
            elif model_id == "animegan_v2":
                self.training_finished_signal.emit("success", "GAN Training finished and weights saved.")
            else:
                self.training_finished_signal.emit("success", "LoRA Training finished and weights saved.")

        except Exception as e:
            # Emit error to main thread
            self.update_status_signal.emit(f"Error: {str(e)}")
            self.training_finished_signal.emit("error", str(e))