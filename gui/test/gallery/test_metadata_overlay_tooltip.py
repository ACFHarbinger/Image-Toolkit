import pytest
from PySide6.QtCore import QObject, QRunnable, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from gui.src.components.virtual_gallery.delegate import VirtualGalleryDelegate
from gui.src.components.virtual_gallery.virtual_gallery_model import VirtualGalleryModel

pytestmark = pytest.mark.gui


class _DummySignals(QObject):
    result = Signal(str, QImage)


class DummyLoaderWorker(QRunnable):
    def __init__(self, path: str, size: int):
        super().__init__()
        self.path = path
        self.size = size
        self.load_generation = 0
        self.signals = _DummySignals()

    def run(self):
        pass


def test_virtual_gallery_model_rich_tooltip(q_app):
    model = VirtualGalleryModel(worker_factory=DummyLoaderWorker, fill_mode=False)
    model.set_paths(["/tmp/sample_image.png"])

    # Basic tooltip
    tip = model.data(model.index(0, 0), Qt.ItemDataRole.ToolTipRole)
    assert "sample_image.png" in tip

    # Set metadata
    model.set_overlay_metadata(
        "/tmp/sample_image.png",
        rating="s",
        resolution=(1920, 1080),
        file_format="PNG",
        star_rating=4.5,
        tag_count=12,
    )

    tip_rich = model.data(model.index(0, 0), Qt.ItemDataRole.ToolTipRole)
    assert "sample_image.png" in tip_rich
    assert "1920 × 1080" in tip_rich
    assert "PNG" in tip_rich
    assert "★ 4.5" in tip_rich
    assert "Tags: 12" in tip_rich


def test_virtual_gallery_delegate_hover_paint(q_app):
    delegate = VirtualGalleryDelegate()
    model = VirtualGalleryModel(worker_factory=DummyLoaderWorker, fill_mode=False)
    model.set_paths(["/tmp/test.jpg"])

    pix = QPixmap(200, 200)
    painter = QPainter(pix)

    option = QStyleOptionViewItem()
    option.rect.setRect(0, 0, 150, 150)
    option.state = QStyle.StateFlag.State_MouseOver

    # Paint should execute cleanly without error
    delegate.paint(painter, option, model.index(0, 0))
    painter.end()
