from backend.src.web.clients.mal_dispatcher import fetch_mal_anime_data
from PySide6.QtCore import Signal

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.windows.settings.app_settings import AppSettings


class MalSyncWorker(BaseQThreadWorker):
    finished = Signal(dict)  # result dict, None on failure/cancel

    def __init__(self, title: str, method: str | None = None):
        super().__init__()
        self.title = title
        self.method = method or AppSettings.mal_fetch_method()

    def _execute(self) -> object:
        result = fetch_mal_anime_data(self.title, method=self.method)
        if "error" in result:
            self.error.emit(result["error"])
            return None
        return result
