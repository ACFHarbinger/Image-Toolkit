import os
import torch

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QFileDialog,
    QTextEdit,
    QGridLayout,
    QMessageBox,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QTimer
from ....helpers import TrainingWorker


class GANTrainTab(QWidget):
    """
    Tab specifically for training the Custom GAN.
    """

    def __init__(self):
        super().__init__()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.training_thread = None
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)

        # --- Parameters ---
        form_layout = QGridLayout()

        # Data Path
        self.txt_data_path = QLineEdit()
        self.txt_data_path.setPlaceholderText(
            "Path to dataset folder (containing subfolders)"
        )
        btn_data_path = QPushButton("Browse")
        btn_data_path.clicked.connect(lambda: self.browse_folder(self.txt_data_path))

        form_layout.addWidget(QLabel("Dataset Path:"), 0, 0)
        form_layout.addWidget(self.txt_data_path, 0, 1)
        form_layout.addWidget(btn_data_path, 0, 2)

        # Save Path
        self.txt_save_path = QLineEdit()
        self.txt_save_path.setText(os.path.join(os.getcwd(), "gan_checkpoints"))
        btn_save_path = QPushButton("Browse")
        btn_save_path.clicked.connect(lambda: self.browse_folder(self.txt_save_path))

        form_layout.addWidget(QLabel("Output Dir:"), 1, 0)
        form_layout.addWidget(self.txt_save_path, 1, 1)
        form_layout.addWidget(btn_save_path, 1, 2)

        # Hyperparams
        self.spin_epochs = QSpinBox()
        self.spin_epochs.setRange(1, 10000)
        self.spin_epochs.setValue(50)

        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(1, 512)
        self.spin_batch.setValue(64)

        self.spin_lr = QDoubleSpinBox()
        self.spin_lr.setRange(0.00001, 0.1)
        self.spin_lr.setDecimals(5)
        self.spin_lr.setValue(0.0002)

        form_layout.addWidget(QLabel("Epochs:"), 2, 0)
        form_layout.addWidget(self.spin_epochs, 2, 1)

        form_layout.addWidget(QLabel("Batch Size:"), 3, 0)
        form_layout.addWidget(self.spin_batch, 3, 1)

        form_layout.addWidget(QLabel("Learning Rate:"), 4, 0)
        form_layout.addWidget(self.spin_lr, 4, 1)

        self.layout.addLayout(form_layout)

        # --- Actions ---
        self.btn_train = QPushButton("Start Training")
        self.btn_train.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;"
        )
        self.btn_train.clicked.connect(self.start_training)
        self.layout.addWidget(self.btn_train)

        # --- Feedback ---
        self.progress_log = QTextEdit()
        self.progress_log.setReadOnly(True)
        self.layout.addWidget(QLabel("Training Log:"))
        self.layout.addWidget(self.progress_log)

        # Preview Area
        self.lbl_preview = QLabel("Latest Training Sample")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("border: 2px dashed #aaa; padding: 10px;")
        self.lbl_preview.setMinimumHeight(200)
        self.layout.addWidget(self.lbl_preview)

        # Timer to update preview
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_training_preview)

    def browse_folder(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if path:
            line_edit.setText(path)

    def log(self, message):
        self.progress_log.append(message)
        sb = self.progress_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def start_training(self):
        data_path = self.txt_data_path.text()
        save_path = self.txt_save_path.text()

        if not data_path or not os.path.exists(data_path):
            QMessageBox.warning(self, "Error", "Invalid Data Path")
            return

        self.btn_train.setEnabled(False)
        self.btn_train.setText("Training in Progress...")
        self.log("Initializing training thread...")

        self.training_thread = TrainingWorker(
            data_path=data_path,
            save_path=save_path,
            epochs=self.spin_epochs.value(),
            batch_size=self.spin_batch.value(),
            lr=self.spin_lr.value(),
            z_dim=100,
            device_name=self.device,
        )

        self.training_thread.log_signal.connect(self.log)
        self.training_thread.error_signal.connect(self.on_training_error)
        self.training_thread.finished_signal.connect(self.on_training_finished)
        self.training_thread.start()

        self.preview_timer.start(5000)

    def on_training_error(self, msg):
        QMessageBox.critical(self, "Training Error", msg)
        self.reset_training_ui()

    def on_training_finished(self):
        QMessageBox.information(self, "Success", "Training Completed Successfully!")
        self.reset_training_ui()

    def reset_training_ui(self):
        self.btn_train.setEnabled(True)
        self.btn_train.setText("Start Training")
        self.preview_timer.stop()

    def update_training_preview(self):
        save_path = self.txt_save_path.text()
        if not os.path.exists(save_path):
            return
        files = sorted(Path(save_path).glob("*_sample.png"), key=os.path.getmtime)
        if files:
            latest_image = str(files[-1])
            pixmap = QPixmap(latest_image)
            if not pixmap.isNull():
                self.lbl_preview.setPixmap(
                    pixmap.scaled(
                        self.lbl_preview.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )

    # Required for Unified Tab integration
    def collect(self):
        return {
            "data_path": self.txt_data_path.text(),
            "save_path": self.txt_save_path.text(),
            "epochs": self.spin_epochs.value(),
            "batch_size": self.spin_batch.value(),
            "lr": self.spin_lr.value(),
        }

    def set_config(self, config):
        if "data_path" in config:
            self.txt_data_path.setText(config["data_path"])
        if "save_path" in config:
            self.txt_save_path.setText(config["save_path"])
        if "epochs" in config:
            self.spin_epochs.setValue(config["epochs"])
        if "batch_size" in config:
            self.spin_batch.setValue(config["batch_size"])
        if "lr" in config:
            self.spin_lr.setValue(config["lr"])
