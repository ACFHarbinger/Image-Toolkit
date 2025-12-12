import threading

from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QComboBox,
    QLabel,
    QWidget,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
)
from ....classes.base_generative_tab import BaseGenerativeTab
from backend.src.models.gan_wrapper import GanWrapper
from backend.src.models.lora_diffusion import LoRATuner
from backend.src.utils.definitions import LOCAL_SOURCE_PATH


class LoRATrainTab(BaseGenerativeTab):
    # --- Define Signals for Thread-Safe Communication ---
    update_status_signal = Signal(str)
    training_finished_signal = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.last_browsed_scan_dir = LOCAL_SOURCE_PATH
        self.init_ui()
        self.update_status_signal.connect(self.handle_status_update)
        self.training_finished_signal.connect(self.handle_training_finished)

    def init_ui(self):
        layout = QFormLayout()

        # --- Model Selection ---
        self.model_selector = QComboBox()
        models = [
            (
                "Illustrious XL V2.0 (Base SDXL)",
                "stabilityai/stable-diffusion-xl-base-1.0",
            ),
            (
                "Illustrious Lumina (Base SDXL)",
                "stabilityai/stable-diffusion-xl-base-1.0",
            ),
            ("Anything V3", "ckpt/anything-v3.0"),
            ("Anything V4.5", "ckpt/anything-v4.5"),
            ("Anything V5", "stablediffusionapi/anything-v5"),
            ("Waifu Diffusion v1.4", "hakurei/waifu-diffusion"),
            ("Counterfeit V2.5", "gsdf/Counterfeit-V2.5"),
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

        self.add_param_widget(
            layout, "Output Name:", QLineEdit("my_model"), "output_name"
        )

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
        self.add_param_widget(
            layout, "Epochs:", QSpinBox(minimum=1, value=5, maximum=100), "epochs"
        )
        self.add_param_widget(
            layout,
            "Batch Size:",
            QSpinBox(minimum=1, value=1, maximum=32),
            "batch_size",
        )

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
        self.cancel_btn.setEnabled(False)
        self.status_label = QLabel("Ready")
        layout.addRow(self.status_label)
        self.setLayout(layout)

    def browse_dataset(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Dataset Folder", self.last_browsed_scan_dir
        )
        if directory:
            self.data_dir_edit.setText(directory)
            self.last_browsed_scan_dir = directory

    def update_ui_visibility(self):
        is_gan = self.model_selector.currentData() == "animegan_v2"
        self.lora_group.setVisible(not is_gan)
        self.cancel_btn.setEnabled(False)

    def cancel_training(self):
        model_id = self.model_selector.currentData()
        if model_id == "animegan_v2":
            GanWrapper.cancel_process()
        else:
            LoRATuner.cancel_process()
        self.cancel_btn.setEnabled(False)
        self.train_btn.setEnabled(True)
        self.handle_status_update("Cancellation requested...")

    # --- Config Methods ---
    def collect(self) -> dict:
        data = super().collect()
        # Add custom fields
        data["dataset_folder"] = self.data_dir_edit.text()
        data["trigger_prompt"] = self.prompt_edit.text()
        data["lora_rank"] = self.rank_box.value()
        # Ensure model_id uses the text representation for the Combo box in base collect,
        # but we might want to ensure the selection is robust. Base collect saves 'currentText'.
        return data

    def set_config(self, config: dict):
        super().set_config(config)
        # Restore custom fields
        if "dataset_folder" in config:
            self.data_dir_edit.setText(config["dataset_folder"])
        if "trigger_prompt" in config:
            self.prompt_edit.setText(config["trigger_prompt"])
        if "lora_rank" in config:
            self.rank_box.setValue(config["lora_rank"])

    def get_default_config(self) -> dict:
        defaults = super().get_default_config()
        defaults.update(
            {
                "dataset_folder": LOCAL_SOURCE_PATH,
                "trigger_prompt": "1girl, style of my_char",
                "lora_rank": 4,
            }
        )
        return defaults

    # --- Slots (Main Thread) ---
    @Slot(str)
    def handle_status_update(self, text):
        self.status_label.setText(text)

    @Slot(str, str)
    def handle_training_finished(self, status_type, message):
        self.train_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        LoRATuner.is_cancelled = False
        GanWrapper.is_cancelled = False
        if status_type == "success":
            self.status_label.setText(message)
            QMessageBox.information(self, "Success", message)
        elif status_type == "cancel":
            self.status_label.setText("Stopped.")
            QMessageBox.warning(self, "Result", message)
        else:
            self.status_label.setText("Error occurred.")
            QMessageBox.critical(self, "Error", message)

    def start_training_thread(self):
        self.train_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("Initializing Training...")
        params = self.collect()  # Use collect instead of get_params for consistency

        config = {
            "params": params,
            "data_dir": self.data_dir_edit.text(),
            "model_id": self.model_selector.currentData(),
            "rank": self.rank_box.value(),
            "prompt": self.prompt_edit.text(),
            "output_name": params.get("output_name", "output_lora"),
        }
        thread = threading.Thread(target=self.run_training, kwargs=config)
        thread.start()

    def run_training(self, params, data_dir, model_id, rank, prompt, output_name):
        try:
            if model_id == "animegan_v2":
                self.update_status_signal.emit("Starting GAN Fine-tuning...")
                gan = GanWrapper()
                gan.train(
                    style_data_dir=data_dir,
                    epochs=params.get("epochs", 5),
                    lr=params.get("learning_rate", 1e-4),
                    batch_size=params.get("batch_size", 1),
                )
                is_cancelled = GanWrapper.is_cancelled
            else:
                self.update_status_signal.emit(
                    f"Loading Diffusion Model: {model_id}..."
                )
                tuner = LoRATuner(model_id=model_id, output_dir=output_name)
                tuner.configure_lora(rank=rank)
                self.update_status_signal.emit("Training started...")
                tuner.train(
                    data_dir=data_dir,
                    instance_prompt=prompt,
                    epochs=params.get("epochs", 5),
                    learning_rate=params.get("learning_rate", 1e-4),
                    batch_size=params.get("batch_size", 1),
                )
                is_cancelled = LoRATuner.is_cancelled

            if is_cancelled:
                self.training_finished_signal.emit(
                    "cancel", "Training process was stopped by the user."
                )
            else:
                self.training_finished_signal.emit(
                    "success", "Training finished and weights saved."
                )
        except Exception as e:
            self.update_status_signal.emit(f"Error: {str(e)}")
            self.training_finished_signal.emit("error", str(e))
