import pytest

from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QWidget, QLabel, QGridLayout, QScrollArea
from gui.src.classes.abstract_class_single_gallery import AbstractClassSingleGallery
from gui.src.classes.abstract_class_two_galleries import AbstractClassTwoGalleries
from gui.src.classes.meta_abstract_class_gallery import MetaAbstractClassGallery

# --- Concrete Implementations / Mocks ---


class ConcreteSingleGallery(AbstractClassSingleGallery):
    def __init__(self):
        super().__init__()
        self.gallery_scroll_area = QScrollArea()
        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout()
        self.gallery_widget.setLayout(self.gallery_layout)
        self.gallery_scroll_area.setWidget(self.gallery_widget)

    def create_card_widget(self, path: str, pixmap: QPixmap = None) -> QWidget:
        label = QLabel(path)
        if pixmap:
            label.setPixmap(pixmap)
        return label

    def update_card_pixmap(self, widget: QWidget, pixmap: QPixmap):
        if isinstance(widget, QLabel) and pixmap:
            widget.setPixmap(pixmap)

    def _generate_video_thumbnail(self, file_path: str):
        return None


class ConcreteTwoGalleries(AbstractClassTwoGalleries):
    def __init__(self):
        super().__init__()
        self.found_gallery_scroll = QScrollArea()
        self.found_gallery_widget = QWidget()
        self.found_gallery_layout = QGridLayout()
        self.found_gallery_widget.setLayout(self.found_gallery_layout)
        self.found_gallery_scroll.setWidget(self.found_gallery_widget)

        self.selected_gallery_scroll = QScrollArea()
        self.selected_gallery_widget = QWidget()
        self.selected_gallery_layout = QGridLayout()
        self.selected_gallery_widget.setLayout(self.selected_gallery_layout)
        self.selected_gallery_scroll.setWidget(self.selected_gallery_widget)

        self.selection_changed_called = 0

    def create_card_widget(
        self, path: str, pixmap: QPixmap, is_selected: bool
    ) -> QWidget:
        label = QLabel(path)
        if pixmap:
            label.setPixmap(pixmap)
        label.setProperty("is_selected", is_selected)
        return label

    def update_card_pixmap(self, widget: QWidget, pixmap: QPixmap):
        if isinstance(widget, QLabel) and pixmap:
            widget.setPixmap(pixmap)

    def on_selection_changed(self):
        self.selection_changed_called += 1


class DummyGallery(QWidget, metaclass=MetaAbstractClassGallery):
    def get_default_config(self) -> dict:
        return {}

    def set_config(self, config: dict):
        pass


# --- Fixtures ---


@pytest.fixture
def gallery(q_app, mock_image_loader_worker, monkeypatch):
    monkeypatch.setattr(
        "gui.src.classes.abstract_class_single_gallery.ImageLoaderWorker",
        mock_image_loader_worker,
    )
    return ConcreteSingleGallery()


@pytest.fixture
def two_galleries(q_app, mock_image_loader_worker, monkeypatch):
    monkeypatch.setattr(
        "gui.src.classes.abstract_class_two_galleries.ImageLoaderWorker",
        mock_image_loader_worker,
    )
    return ConcreteTwoGalleries()


@pytest.fixture
def dummy_gallery(q_app):
    return DummyGallery()


# --- Test Classes ---


class TestAbstractClassSingleGallery:
    def test_initial_state(self, gallery):
        assert gallery.gallery_image_paths == []
        assert gallery.current_page == 0
        assert gallery.page_size == 100

    def test_pagination_logic(self, gallery):
        gallery.gallery_image_paths = [f"img_{i}.jpg" for i in range(250)]

        assert gallery.current_page == 0
        gallery._change_page(1)
        assert gallery.current_page == 1
        gallery._change_page(1)
        assert gallery.current_page == 2
        gallery._change_page(1)
        assert gallery.current_page == 2
        gallery._change_page(-1)
        assert gallery.current_page == 1

    def test_perform_search(self, gallery):
        gallery.master_image_paths = ["apple.jpg", "banana.jpg", "cherry.png"]
        gallery.gallery_image_paths = list(gallery.master_image_paths)

        gallery.search_input.setText("apple")
        gallery._perform_search()
        assert gallery.gallery_image_paths == ["apple.jpg"]

        gallery.search_input.setText("jpg")
        gallery._perform_search()
        assert len(gallery.gallery_image_paths) == 2

    def test_loading_flow(self, gallery, mock_pixmap):
        paths = ["test1.jpg", "test2.jpg"]
        gallery.start_loading_gallery(paths)

        assert gallery.master_image_paths == paths
        assert gallery.gallery_image_paths == paths

        gallery._populate_step()
        assert len(gallery.path_to_card_widget) == 2
        assert "test1.jpg" in gallery.path_to_card_widget

    def test_threading_mock_integration(self, gallery):
        path = "test_image.jpg"
        gallery.gallery_image_paths = [path]
        gallery._paginated_paths = [path]

        gallery._populate_step()
        widget = gallery.path_to_card_widget[path]

        assert widget.pixmap() is None or widget.pixmap().isNull()

        qimg = QImage(10, 10, QImage.Format_RGB32)
        gallery._on_single_image_loaded(path, qimg)
        assert widget.pixmap() is not None


class TestAbstractClassTwoGalleries:
    def test_initial_state(self, two_galleries):
        assert two_galleries.found_files == []
        assert two_galleries.selected_files == []
        assert two_galleries.found_current_page == 0

    def test_selection_logic(self, two_galleries):
        path = "test.jpg"
        two_galleries.found_files = [path]

        two_galleries.toggle_selection(path)
        assert path in two_galleries.selected_files
        assert two_galleries.selection_changed_called == 1

        two_galleries.toggle_selection(path)
        assert path not in two_galleries.selected_files
        assert two_galleries.selection_changed_called == 2

    def test_select_all_deselect_all(self, two_galleries):
        paths = [f"img_{i}.jpg" for i in range(50)]
        two_galleries.found_files = paths
        two_galleries.found_page_size = 100

        two_galleries.select_all_items()
        assert len(two_galleries.selected_files) == 50
        assert two_galleries.selection_changed_called > 0

        two_galleries.deselect_all_items()
        assert len(two_galleries.selected_files) == 0

    def test_pagination_found(self, two_galleries):
        two_galleries.found_files = [f"img_{i}.jpg" for i in range(150)]
        two_galleries.found_page_size = 100

        two_galleries._change_page(1, is_found=True)
        assert two_galleries.found_current_page == 1

        two_galleries._change_page(1, is_found=True)
        assert two_galleries.found_current_page == 1

    def test_pagination_selected(self, two_galleries):
        two_galleries.selected_files = [f"img_{i}.jpg" for i in range(150)]
        two_galleries._change_page(1, is_found=False)
        assert two_galleries.selected_current_page == 1

    def test_loading_found_gallery(self, two_galleries):
        paths = ["a.jpg", "b.jpg"]
        two_galleries.start_loading_thumbnails(paths)

        assert two_galleries.master_found_files == paths
        assert two_galleries.found_files == paths

        two_galleries._populate_found_step()
        assert len(two_galleries.path_to_label_map) == 2
        assert "a.jpg" in two_galleries.path_to_label_map


class TestMetaAbstractClassGallery:
    def test_method_injection(self, dummy_gallery):
        assert hasattr(dummy_gallery, "common_create_pagination_ui")
        assert hasattr(dummy_gallery, "common_calculate_columns")
        assert hasattr(dummy_gallery, "common_filter_string_list")

    def test_common_filter_string_list(self, dummy_gallery):
        data = ["Apple", "Banana", "Apricot", "Cherry"]

        filtered = dummy_gallery.common_filter_string_list(data, "ap")
        assert "Apple" in filtered
        assert "Apricot" in filtered
        assert "Banana" not in filtered

        assert dummy_gallery.common_filter_string_list(data, "") == data
        assert dummy_gallery.common_filter_string_list(data, "xyz") == []

    def test_common_calculate_columns(self, dummy_gallery):
        scroll = QScrollArea()
        scroll.resize(1000, 500)
        cols = dummy_gallery.common_calculate_columns(scroll, 200)
        assert cols > 0

    def test_common_join_list_str(self, dummy_gallery):
        res = MetaAbstractClassGallery.join_list_str("a, b, c")
        assert res == ["a", "b", "c"]

        res = MetaAbstractClassGallery.join_list_str("foo bar .baz")
        assert res == ["foo", "bar", "baz"]
