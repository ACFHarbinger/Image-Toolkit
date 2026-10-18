"""Image sub-tab source gallery (images + GIFs), like the Video sub-tab's."""

import pytest
from PIL import Image

from gui.src.tabs.core.image_extractor_gallery import SOURCE_GALLERY_HEIGHT, list_source_images
from gui.src.tabs.core.image_extractor_subtab import ImageExtractorSubTab

pytestmark = pytest.mark.gui


@pytest.fixture
def media_dir(tmp_path):
    for name in ("frame10.png", "frame2.jpg", "anim.gif"):
        Image.new("RGB", (64, 32), (10, 20, 30)).save(tmp_path / name)
    (tmp_path / "clip.mp4").write_bytes(b"\x00")
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    return tmp_path


def test_lists_images_and_gifs_only_in_natural_order(media_dir):
    names = [p.rsplit("/", 1)[-1] for p in list_source_images(str(media_dir))]
    assert names == ["anim.gif", "frame2.jpg", "frame10.png"]
    assert list_source_images(str(media_dir / "missing")) == []


def test_gallery_scan_click_and_config_round_trip(q_app, media_dir):
    tab = ImageExtractorSubTab()
    tab.resize(1000, 900)
    tab.show()
    gallery = tab.source_gallery

    assert gallery.gallery.height() == SOURCE_GALLERY_HEIGHT
    assert gallery.gallery._height_resizer is not None

    assert gallery.scan_directory(str(media_dir))
    assert gallery.gallery.count() == 3
    assert gallery.gallery_group.title() == "Available Images (3)"

    gif = str(media_dir / "anim.gif")
    gallery.gallery.path_clicked.emit(gif)
    assert tab.image_path == gif
    assert tab.line_edit_image.text() == gif
    assert gallery.gallery.is_preview(gif)

    config = tab.collect()
    assert config["source_directory"] == str(media_dir)
    tab.close()

    restored = ImageExtractorSubTab()
    restored.set_config(config)
    assert restored.source_gallery.source_dir == str(media_dir)
    assert restored.source_gallery.gallery.count() == 3
    assert restored.image_path == gif
    restored.close()


def test_gallery_height_drag_resizes(q_app, media_dir):
    tab = ImageExtractorSubTab()
    tab.show()
    resizer = tab.source_gallery.gallery._height_resizer
    resizer.begin_drag(100)
    resizer.drag_to("bottom", 180)
    resizer.end_drag()
    assert tab.source_gallery.gallery.height() == SOURCE_GALLERY_HEIGHT + 80
    resizer.reset()
    assert tab.source_gallery.gallery.height() == SOURCE_GALLERY_HEIGHT
    tab.close()
