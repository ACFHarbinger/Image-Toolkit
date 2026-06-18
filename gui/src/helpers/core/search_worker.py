from gui.src.helpers.base import BaseQRunnableWorker


class SearchWorker(BaseQRunnableWorker):
    """Runs the blocking database search query off the main thread."""

    def __init__(self, db, query_params):
        super().__init__()
        self.db = db
        self.query_params = query_params

    def _execute(self) -> None:
        matching_files = self.db.search_images(**self.query_params)
        if self._cancelled:
            self.signals.cancelled.emit()
        else:
            self.signals.finished.emit(matching_files)
