import os
import torch

from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QSpinBox,
    QFileDialog,
    QFrame,
    QScrollArea,
    QGridLayout,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap, QImage
from backend.src.models.gan import GAN


class GANGenerateTab(QWidget):
    """
    Tab specifically for generating images using the Custom GAN.
    """

    def __init__(self):
        super().__init__()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)

        # --- Input ---
        form_layout = QHBoxLayout()
        self.txt_checkpoint = QLineEdit()
        self.txt_checkpoint.setPlaceholderText("Path to .pth checkpoint file")
        btn_ckpt = QPushButton("Browse")
        btn_ckpt.clicked.connect(lambda: self.browse_file(self.txt_checkpoint))

        form_layout.addWidget(QLabel("Checkpoint:"))
        form_layout.addWidget(self.txt_checkpoint)
        form_layout.addWidget(btn_ckpt)
        self.layout.addLayout(form_layout)

        control_layout = QHBoxLayout()
        self.spin_gen_count = QSpinBox()
        self.spin_gen_count.setRange(1, 64)
        self.spin_gen_count.setValue(8)

        self.btn_generate = QPushButton("Generate Images")
        self.btn_generate.clicked.connect(self.generate_images)

        control_layout.addWidget(QLabel("Count:"))
        control_layout.addWidget(self.spin_gen_count)
        control_layout.addWidget(self.btn_generate)
        self.layout.addLayout(control_layout)

        # --- Display Grid ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.gen_container = QWidget()
        self.gen_grid = QGridLayout(self.gen_container)
        self.scroll_area.setWidget(self.gen_container)
        self.layout.addWidget(self.scroll_area)

    def browse_file(self, line_edit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Checkpoint", "", "PyTorch Models (*.pth *.pt)"
        )
        if path:
            line_edit.setText(path)

    def generate_images(self):
        checkpoint_path = self.txt_checkpoint.text()
        if not os.path.exists(checkpoint_path):
            QMessageBox.warning(self, "Error", "Checkpoint file not found.")
            return

        try:
            for i in reversed(range(self.gen_grid.count())):
                self.gen_grid.itemAt(i).widget().setParent(None)

            device = torch.device(self.device)
            gan = GAN(z_dim=100, channels=3, n_filters=32, n_blocks=3, device=device)
            gan.load_checkpoint(checkpoint_path)

            count = self.spin_gen_count.value()
            images_tensor = gan.generate_image(num_images=count)
            images_tensor = images_tensor.cpu()

            row, col = 0, 0
            cols_per_row = 4

            for i in range(count):
                img_t = images_tensor[i]
                img_np = img_t.permute(1, 2, 0).numpy()
                img_np = (img_np * 255).astype("uint8")

                height, width, channel = img_np.shape
                bytes_per_line = 3 * width
                q_img = QImage(
                    img_np.data, width, height, bytes_per_line, QImage.Format_RGB888
                )

                lbl = QLabel()
                pixmap = QPixmap.fromImage(q_img)
                lbl.setPixmap(pixmap.scaled(128, 128, Qt.KeepAspectRatio))
                lbl.setFrameShape(QFrame.Box)

                self.gen_grid.addWidget(lbl, row, col)
                col += 1
                if col >= cols_per_row:
                    col = 0
                    row += 1

        except Exception as e:
            QMessageBox.critical(self, "Generation Error", str(e))

    # Required for Unified Tab integration
    def collect(self):
        return {
            "checkpoint_path": self.txt_checkpoint.text(),
            "gen_count": self.spin_gen_count.value(),
        }

    def set_config(self, config):
        if "checkpoint_path" in config:
            self.txt_checkpoint.setText(config["checkpoint_path"])
        if "gen_count" in config:
            self.spin_gen_count.setValue(config["gen_count"])

    @Slot(str, int)
    def generate_from_qml(self, checkpoint_path, count):
        """Wrapper to call generation from QML"""
        self.txt_checkpoint.setText(checkpoint_path)
        self.spin_gen_count.setValue(count)
        # Call existing generation method (runs on main thread currently as per original implementation)
        # For better UX, might want to move to thread, but keeping logic consistent with original for now.
        self.generate_images()
