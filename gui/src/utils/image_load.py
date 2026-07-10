"""Shared image loading helpers for formats Qt may not decode natively."""

from __future__ import annotations

from pathlib import Path

from backend.src.constants import SUPPORTED_IMG_FORMATS
from PySide6.QtGui import QImage, QImageReader

_QT_NATIVE_EXTS = {
    fmt.data().decode().lower() for fmt in QImageReader.supportedImageFormats()
}

IMAGE_FILE_DIALOG_FILTER = (
    "Images ("
    + " ".join(f"*.{fmt}" for fmt in SUPPORTED_IMG_FORMATS)
    + ")"
)


def load_qimage(path: str) -> QImage:
    """Load an image as QImage, using Pillow when Qt has no decoder (e.g. AVIF)."""
    if not path:
        return QImage()

    img = QImage(path)
    if not img.isNull():
        return img

    ext = Path(path).suffix.lower().lstrip(".")
    if ext not in SUPPORTED_IMG_FORMATS and ext not in _QT_NATIVE_EXTS:
        return QImage()

    try:
        from PIL import Image

        with Image.open(path) as pil_img:
            rgb = pil_img.convert("RGB")
            data = rgb.tobytes()
            w, h = rgb.size
            return QImage(data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
    except Exception:
        return QImage()