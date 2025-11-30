from PySide6.QtCore import Signal, QObject, QRunnable
from backend.src.web import ReverseImageSearchCrawler


class ReverseSearchWorkerSignals(QObject):
    finished = Signal(list)
    error = Signal(str)
    status = Signal(str)


class ReverseSearchWorker(QRunnable):
    """
    Worker thread to run the Selenium crawler without freezing the GUI.
    """
    def __init__(self, image_path: str, min_width: int, min_height: int, browser: str):
        super().__init__()
        self.image_path = image_path
        self.min_width = min_width
        self.min_height = min_height
        self.browser = browser
        self.signals = ReverseSearchWorkerSignals()

    def run(self):
        crawler = None
        try:
            self.signals.status.emit("Initializing Browser...")
            crawler = ReverseImageSearchCrawler(headless=False, browser=self.browser)
            
            self.signals.status.emit("Uploading & Searching...")
            results = crawler.perform_reverse_search(self.image_path, self.min_width, self.min_height)
            
            self.signals.finished.emit(results)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            if crawler:
                self.signals.status.emit("Closing Browser...")
                crawler.close()