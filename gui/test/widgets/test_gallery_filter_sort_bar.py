"""Unit tests for GalleryFilterSortBar and VirtualGalleryModel filtering & sorting (§2.13)."""

import pytest
from gui.src.components.gallery.virtual_gallery_model import VirtualGalleryModel
from gui.src.components.widgets.gallery_filter_sort_bar import GalleryFilterSortBar
from PySide6.QtCore import QObject, Signal


class DummySignals(QObject):
    result = Signal(str, object)


class DummyLoaderWorker(QObject):
    def __init__(self, path: str, size: int):
        super().__init__()
        self.path = path
        self.size = size
        self.load_generation = 0
        self.signals = DummySignals()


@pytest.fixture
def sample_paths(tmp_path):
    files = [
        tmp_path / "image10.png",
        tmp_path / "image2.jpg",
        tmp_path / "image1.webp",
        tmp_path / "draft_sample.png",
        tmp_path / "final_art.jpg",
    ]
    for idx, f in enumerate(files):
        f.write_text(f"dummy data {idx}")
    return [str(f) for f in files]


@pytest.mark.gui
def test_virtual_gallery_model_sorting(q_app, sample_paths):
    model = VirtualGalleryModel(worker_factory=DummyLoaderWorker, fill_mode=False)
    model.set_paths(sample_paths)
    assert model.rowCount() == 5

    # Natural sort by name ascending: image1, image2, image10, draft_sample, final_art
    model.sort_by("name", reverse=False)
    names = [model.data(model.index(i, 0), model.PathRole).split("/")[-1] for i in range(model.rowCount())]
    assert names[0] == "draft_sample.png"
    assert "image1.webp" in names
    assert names.index("image2.jpg") < names.index("image10.png")

    # Sort by name descending
    model.sort_by("name", reverse=True)
    rev_names = [model.data(model.index(i, 0), model.PathRole).split("/")[-1] for i in range(model.rowCount())]
    assert rev_names[0] != names[0]


@pytest.mark.gui
def test_virtual_gallery_model_filtering(q_app, sample_paths):
    model = VirtualGalleryModel(worker_factory=DummyLoaderWorker, fill_mode=False)
    model.set_paths(sample_paths)

    # Filter by extension: only PNG
    model.filter_by(extensions={"png"})
    assert model.rowCount() == 2
    for i in range(model.rowCount()):
        assert model.data(model.index(i, 0), model.PathRole).endswith(".png")

    # Filter by query negation: -draft
    model.filter_by(extensions=None, query="-draft")
    assert model.rowCount() == 4
    for i in range(model.rowCount()):
        assert "draft" not in model.data(model.index(i, 0), model.PathRole)

    # Filter by OR query: image1|image2
    model.filter_by(query="image1|image2")
    assert model.rowCount() == 3  # image1.webp, image2.jpg, image10.png


@pytest.mark.gui
def test_gallery_filter_sort_bar_widget(q_app, sample_paths):
    model = VirtualGalleryModel(worker_factory=DummyLoaderWorker, fill_mode=False)
    model.set_paths(sample_paths)

    bar = GalleryFilterSortBar()
    bar.bind_gallery(model)
    bar.update_formats_from_paths(sample_paths)

    # Sort change
    bar.sort_combo.setCurrentText("Extension")
    exts = [model.data(model.index(i, 0), model.PathRole).split(".")[-1] for i in range(model.rowCount())]
    assert exts == sorted(exts)

    # Direction toggle
    bar.sort_dir_btn.click()
    rev_exts = [model.data(model.index(i, 0), model.PathRole).split(".")[-1] for i in range(model.rowCount())]
    assert rev_exts == sorted(exts, reverse=True)

    # Format chip click
    bar._ext_buttons["png"].click()
    assert model.rowCount() == 2

    # Click ALL formats
    bar.all_formats_btn.click()
    assert model.rowCount() == 5

    # Text search
    bar.search_edit.setText("final")
    assert model.rowCount() == 1
    assert model.data(model.index(0, 0), model.PathRole).endswith("final_art.jpg")
