from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from gui.src.theming.theme_api import qss


class QueueItemView(QWidget):
    """A widget to display an image preview and its name in the queue."""

    def __init__(self, path: str, pixmap: QPixmap, index: int = 0, parent=None):
        super().__init__(parent)
        self.path = path

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Index Label
        self.index_label = QLabel(f"{index}.")
        self.index_label.setFixedWidth(30)
        self.index_label.setStyleSheet(qss("queue_index_label"))
        self.index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.index_label)

        # Image Preview Label
        img_label = QLabel()
        img_label.setPixmap(
            pixmap.scaled(QSize(80, 60), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
        img_label.setFixedSize(80, 60)
        img_label.setStyleSheet(qss("queue_thumb_frame"))
        layout.addWidget(img_label)

        # Filename Label
        filename = Path(path).name
        file_label = QLabel(filename)
        file_label.setToolTip(path)
        file_label.setStyleSheet(qss("queue_filename"))
        file_label.setWordWrap(True)
        layout.addWidget(file_label, 1)

        self.setLayout(layout)
        self.setFixedSize(QSize(380, 70))

    def update_index(self, index: int):
        """Update the displayed index label."""
        self.index_label.setText(f"{index}.")
