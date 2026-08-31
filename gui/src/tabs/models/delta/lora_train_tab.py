import subprocess
import sys
import threading

from backend.src.constants import LOCAL_SOURCE_PATH, ROOT_DIR
from backend.src.models.tuning.lo_ra_tuner import LoRATuner
from backend.src.models.wrappers.gan_wrapper import GanWrapper
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
)

from ....classes.base.base_generative_tab import BaseGenerativeTab

# Content Gen §1.3: LyCORIS variants (LoCon/LoHa/LoKr), each a Hydra config
# preset under backend/config/training/. "standard" keeps the existing
# LoRATuner (legacy) path byte-for-byte unchanged; the three LyCORIS
# entries route through the already-built LoRATunerV2 pipeline
# (backend/src/pipeline/anime_training_pipeline.py) via the project's own
# Hydra CLI dispatcher, rather than re-implementing dataset/tuner
# construction inline here.
_TRAINING_ENGINES = [
    ("Standard (LoRA)", "standard"),
    ("LyCORIS: LoCon (style-bound characters)", "locon"),
    ("LyCORIS: LoHa (small datasets)", "loha"),
    ("LyCORIS: LoKr (tiny datasets / storage-constrained)", "lokr"),
]


class LoRATrainTab(BaseGenerativeTab):
    # --- Define Signals for Thread-Safe Communication ---
    update_status_signal = Signal(str)
    training_finished_signal = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.last_browsed_scan_dir = LOCAL_SOURCE_PATH
        self._lycoris_process: subprocess.Popen | None = None
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

        # --- Training Engine (Content Gen §1.3: LyCORIS variants) ---
        self.engine_combo = QComboBox()
        for name, engine_id in _TRAINING_ENGINES:
            self.engine_combo.addItem(name, engine_id)
        self.engine_combo.setToolTip(
            "Standard uses this project's original LoRA trainer, unchanged.\n"
            "LyCORIS options route through the LoRATunerV2 pipeline (Hydra\n"
            "presets under backend/config/training/) for LoCon/LoHa/LoKr\n"
            "adaptation instead of plain LoRA — see content_generation.md §1.3."
        )
        self.add_param_widget(layout, "Training Engine:", self.engine_combo, "engine")

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

        inspect_btn = QPushButton("Inspect .safetensors...")
        inspect_btn.setToolTip("Open a .safetensors file and view its metadata")
        inspect_btn.clicked.connect(self._inspect_safetensors)
        button_layout.addWidget(inspect_btn)

        review_tags_btn = QPushButton("Review Tags...")
        review_tags_btn.setToolTip(
            "Run the WD14 auto-tagger over the dataset folder and review/"
            "correct predicted tags before training (new_features.md §4.4C)"
        )
        review_tags_btn.clicked.connect(self._review_tags)
        button_layout.addWidget(review_tags_btn)

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
        if self._lycoris_process is not None:
            self._lycoris_process.terminate()
        else:
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
            "engine": self.engine_combo.currentData(),
        }
        thread = threading.Thread(target=self.run_training, kwargs=config, daemon=True)
        thread.start()

    def run_training(self, params, data_dir, model_id, rank, prompt, output_name, engine="standard"):
        if engine != "standard" and model_id != "animegan_v2":
            self._run_lycoris_training(data_dir, model_id, prompt, output_name, engine)
            return

        gan = None
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
        finally:
            if gan is not None:
                gan.unload()

    def _run_lycoris_training(
        self, data_dir: str, model_id: str, prompt: str, output_name: str, engine: str
    ) -> None:
        """Content Gen §1.3: LyCORIS (LoCon/LoHa/LoKr) training.

        Routes through the already-built LoRATunerV2 pipeline
        (backend/src/pipeline/anime_training_pipeline.py) via this
        project's own Hydra CLI dispatcher, rather than re-implementing
        dataset/tuner construction here — that pipeline already handles
        aspect-ratio bucketing, caption building, and LyCORIS dispatch
        (LoRATunerV2 already supports 'locon'/'loha'/'lokr'/'dylora' via
        `cfg.method == "lycoris"`; only GUI exposure was missing).
        """
        self.update_status_signal.emit(
            f"Launching LyCORIS ({engine}) training via anime_training_pipeline..."
        )
        if getattr(sys, "frozen", False):
            self.update_status_signal.emit(
                "Error: LyCORIS training spawns the source checkout's Hydra "
                "dispatcher and is not available in the packaged build."
            )
            self.training_finished_signal.emit(
                "error", "LyCORIS training requires a source checkout."
            )
            return
        cmd = [
            sys.executable,
            "-m",
            "backend.controllers.hydra_dispatch",
            "command=train",
            f"training=lycoris_{engine}",
            f"model.model_id={model_id}",
            f"data.images_dir={data_dir}",
            f"data.trigger_word={prompt}",
            f"output_dir={output_name}",
        ]
        try:
            self._lycoris_process = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert self._lycoris_process.stdout is not None
            for line in self._lycoris_process.stdout:
                line = line.rstrip()
                if line:
                    self.update_status_signal.emit(line[-200:])
            returncode = self._lycoris_process.wait()

            if returncode == 0:
                self.training_finished_signal.emit(
                    "success", "LyCORIS training finished and weights saved."
                )
            elif returncode < 0:
                # Negative = killed by signal (terminate()/Cancel button).
                self.training_finished_signal.emit(
                    "cancel", "Training process was stopped by the user."
                )
            else:
                self.training_finished_signal.emit(
                    "error", f"Training process exited with code {returncode}."
                )
        except Exception as e:
            self.update_status_signal.emit(f"Error: {str(e)}")
            self.training_finished_signal.emit("error", str(e))
        finally:
            self._lycoris_process = None

    def _inspect_safetensors(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select .safetensors File",
            self.last_browsed_scan_dir,
            "Safetensors models (*.safetensors)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        from gui.src.components.dialogs.safetensors_inspector_dialog import SafetensorsInspectorDialog
        SafetensorsInspectorDialog(path=path, parent=self).exec()

    def _review_tags(self) -> None:
        from pathlib import Path

        data_dir = self.data_dir_edit.text().strip()
        if not data_dir or not Path(data_dir).is_dir():
            QMessageBox.warning(
                self, "Review Tags", "Select a valid dataset folder first."
            )
            return

        exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        image_paths = sorted(
            p for p in Path(data_dir).iterdir() if p.suffix.lower() in exts
        )
        if not image_paths:
            QMessageBox.information(
                self, "Review Tags", "No images found in the dataset folder."
            )
            return

        from gui.src.components.dialogs.tag_review_dialog import TagReviewDialog

        # Note: self.prompt_edit holds a full instance-prompt string (e.g.
        # "1girl, style of my_char"), not a single trigger token like
        # HybridCaptioner's trigger concept — reusing it here would risk
        # duplicating content already covered by the WD tags. Leave the
        # caption trigger unset; the user can add one via the dialog's
        # "Add tag" field if they want a unique activation token.
        TagReviewDialog(image_paths, parent=self).exec()
