from PySide6.QtCore import QThread, Signal
from backend.src.web.jikan_client import fetch_mal_anime_data


class MalSyncWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, title: str):
        super().__init__()
        self.title = title

    def run(self):
        result = fetch_mal_anime_data(self.title)
        if "error" in result:
            self.error.emit(result["error"])
        else:
            self.finished.emit(result)
