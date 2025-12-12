from PySide6.QtCore import Signal, QObject, QRunnable, Slot


class SearchWorkerSignals(QObject):
    """Defines signals available from a running worker thread."""

    finished = Signal(list)
    error = Signal(str)
    cancelled = Signal()


class SearchWorker(QRunnable):
    """Runs the blocking database search query off the main thread."""

    def __init__(self, db, query_params):
        super().__init__()
        self.db = db
        self.query_params = query_params
        self.signals = SearchWorkerSignals()
        self._is_cancelled = False

    @Slot()
    def run(self):
        try:
            if self._is_cancelled:
                self.signals.cancelled.emit()
                return

            # This is the blocking call moved off the main thread
            matching_files = self.db.search_images(**self.query_params)

            if not self._is_cancelled:
                self.signals.finished.emit(matching_files)
            else:
                self.signals.cancelled.emit()
        except Exception as e:
            if not self._is_cancelled:
                self.signals.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True
