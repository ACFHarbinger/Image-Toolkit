from backend.src.web.clients.mal_dispatcher import fetch_mal_anime_data
from gui.src.windows.settings.app_settings import AppSettings
from PySide6.QtCore import QThread, Signal


class MalSyncWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, title: str, method: str | None = None):
        super().__init__()
        self.title = title
        self.method = method or AppSettings.mal_fetch_method()

    def run(self):
        result = fetch_mal_anime_data(self.title, method=self.method)
        if "error" in result:
            self.error.emit(result["error"])
        else:
            self.finished.emit(result)
