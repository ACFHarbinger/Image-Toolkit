"""Small Qt platform helpers owned by the standalone GUI package.

Named ``qt_platform`` rather than ``platform`` to avoid shadowing the stdlib
``platform`` module: pytest adds ``gui/src`` to ``sys.path`` for tests, which
would otherwise make this file importable as the top-level ``platform`` module
in subprocess workers (such as ARAP solver processes), breaking ``uuid``'s
``platform.system()`` call on Python 3.11.
"""

from __future__ import annotations

from PySide6.QtGui import QImage, QImageReader
from PySide6.QtWidgets import QFileDialog

DIALOG_OPTS = QFileDialog.Option.DontUseNativeDialog

_QT_NATIVE_EXTS = sorted(
    bytes(fmt.data()).decode().lower() for fmt in QImageReader.supportedImageFormats()
)
IMAGE_FILE_DIALOG_FILTER = "Images (" + " ".join(f"*.{ext}" for ext in _QT_NATIVE_EXTS) + ")"


def load_qimage(path: str) -> QImage:
    """Load an image with Qt and optionally Pillow for unsupported formats."""
    if not path:
        return QImage()

    image = QImage(path)
    if not image.isNull():
        return image

    try:
        from PIL import Image

        with Image.open(path) as pil_image:
            rgb = pil_image.convert("RGB")
            data = rgb.tobytes()
            width, height = rgb.size
            return QImage(
                data,
                width,
                height,
                3 * width,
                QImage.Format.Format_RGB888,
            ).copy()
    except Exception:
        # An unknown extension or decoder error has the same caller-facing
        # meaning as Qt's null image result.
        return QImage()


__all__ = ["DIALOG_OPTS", "IMAGE_FILE_DIALOG_FILTER", "load_qimage"]
