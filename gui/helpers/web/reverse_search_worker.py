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

    def __init__(
        self,
        image_path: str,
        min_width: int,
        min_height: int,
        browser: str,
        search_mode: str = "All",
        keep_open: bool = False,
    ):
        super().__init__()
        self.image_path = image_path
        self.min_width = min_width
        self.min_height = min_height
        self.browser = browser
        self.search_mode = search_mode
        self.keep_open = keep_open
        self.signals = ReverseSearchWorkerSignals()

    def run(self):
        crawler = None
        try:
            self.signals.status.emit("Initializing Browser...")
            # We initialize the crawler
            crawler = ReverseImageSearchCrawler(headless=False, browser=self.browser)

            self.signals.status.emit(f"Uploading & Searching ({self.search_mode})...")

            # Pass the search mode to the crawler
            results = crawler.perform_reverse_search(
                self.image_path,
                self.min_width,
                self.min_height,
                search_mode=self.search_mode,
            )

            self.signals.finished.emit(results)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            # --- LOGIC TO KEEP BROWSER OPEN ---
            if crawler:
                if not self.keep_open:
                    self.signals.status.emit("Closing Browser...")
                    crawler.close()
                else:
                    self.signals.status.emit("Browser left open by user request.")
                    # We simply do NOT call crawler.close().
                    # The Python object 'crawler' will be garbage collected,
                    # but typically Selenium drivers launched without 'detach' logic
                    # might close. However, assuming the process stays alive,
                    # or the user simply wants to see the result before manual closing, this is sufficient.
