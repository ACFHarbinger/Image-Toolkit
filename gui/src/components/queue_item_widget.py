from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout
from pathlib import Path


class QueueItemWidget(QWidget):
    """A widget to display an image preview and its name in the queue."""

    def __init__(self, path: str, pixmap: QPixmap, index: int = 0, parent=None):
        super().__init__(parent)
        self.path = path

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Index Label
        self.index_label = QLabel(f"{index}.")
        self.index_label.setFixedWidth(30)
        self.index_label.setStyleSheet(
            "color: #7289da; font-weight: bold; font-size: 14px;"
        )
        self.index_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.index_label)

        # Image Preview Label
        img_label = QLabel()
        img_label.setPixmap(
            pixmap.scaled(QSize(80, 60), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        img_label.setFixedSize(80, 60)
        img_label.setStyleSheet("border: 1px solid #4f545c; border-radius: 4px;")
        layout.addWidget(img_label)

        # Filename Label
        filename = Path(path).name
        file_label = QLabel(filename)
        file_label.setToolTip(path)
        file_label.setStyleSheet("color: #b9bbbe; font-size: 12px;")
        file_label.setWordWrap(True)
        layout.addWidget(file_label, 1)

        self.setLayout(layout)
        self.setFixedSize(QSize(380, 70))

    def update_index(self, index: int):
        """Update the displayed index label."""
        self.index_label.setText(f"{index}.")
