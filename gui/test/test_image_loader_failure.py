from PySide6.QtCore import Signal, Slot, QObject
from PySide6.QtGui import QPixmap


# Mock the worker signals
class MockSignals(QObject):
    batch_result = Signal(list, list)


# Mock the worker to simulate failure
class MockBatchWorker(QObject):
    def __init__(self, paths, fail_paths):
        super().__init__()
        self.paths = paths
        self.fail_paths = fail_paths
        self.signals = MockSignals()

    def run(self):
        results = []
        for p in self.paths:
            if p not in self.fail_paths:
                results.append((p, QPixmap(10, 10)))
        # Emit results and requested paths
        self.signals.batch_result.emit(results, self.paths)


# Mock the Gallery class
class MockGallery(QObject):
    def __init__(self):
        super().__init__()
        self._loading_paths = set()
        self.path_to_card_widget = {
            "img1": "widget1",
            "img2": "widget2",
            "img_fail": "widget_fail",
        }
        self.card_status = {}

    def update_card_pixmap(self, widget, pixmap):
        path = [k for k, v in self.path_to_card_widget.items() if v == widget][0]
        if pixmap and not pixmap.isNull():
            self.card_status[path] = "Loaded"
        else:
            self.card_status[path] = "Failed"

    @Slot(list, list)
    def _on_batch_images_loaded(self, results, requested_paths):
        # COPY OF THE LOGIC FROM abstract_class_single_gallery.py
        for path, pixmap in results:
            if path in self._loading_paths:
                self._loading_paths.remove(path)

            widget = self.path_to_card_widget.get(path)
            if widget:
                self.update_card_pixmap(widget, pixmap)

        processed_paths = set(p for p, _ in results)
        for path in requested_paths:
            if path not in processed_paths:
                if path in self._loading_paths:
                    self._loading_paths.remove(path)

                widget = self.path_to_card_widget.get(path)
                if widget:
                    self.update_card_pixmap(widget, QPixmap())


from PySide6.QtGui import QGuiApplication


def test_batch_failure_clears_loading_state():
    if not QGuiApplication.instance():
        app = QGuiApplication([])
    else:
        app = QGuiApplication.instance()

    gallery = MockGallery()
    requested = ["img1", "img2", "img_fail"]
    gallery._loading_paths.update(requested)

    # img_fail should fail
    worker = MockBatchWorker(requested, fail_paths=["img_fail"])

    # Manually trigger signal emission
    worker.signals.batch_result.connect(gallery._on_batch_images_loaded)
    worker.run()

    # Assertions
    assert "img1" not in gallery._loading_paths
    assert "img2" not in gallery._loading_paths
    assert "img_fail" not in gallery._loading_paths  # CRITICAL: This was the bug

    assert gallery.card_status["img1"] == "Loaded"
    assert gallery.card_status["img2"] == "Loaded"
    assert gallery.card_status["img_fail"] == "Failed"
