"""
QRunnable worker for Qdrant-based listing lexical/sparse text search.

Uses BGE-M3 to encode the query string into a sparse vector and then
performs a Qdrant sparse search, optionally filtered by payload criteria.
"""
import logging

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

logger = logging.getLogger(__name__)


class ListingSearchWorkerSignals(QObject):
    finished = Signal(list)   # List[str] – UUIDs in relevance order
    error = Signal(str)
    status = Signal(str)


class ListingSearchWorker(QRunnable):
    """
    Off-thread sparse (lexical) listing search.

    Encodes *query_text* with BGE-M3 sparse weights and performs a
    Qdrant sparse vector search.  Optionally applies Qdrant payload
    filters built from *criteria* (type / status / year).

    Emits ``signals.finished`` with a list of listing UUIDs ordered by
    descending relevance score.
    """

    def __init__(self, qdrant_manager, query_text: str, criteria: dict | None = None):
        super().__init__()
        self.setAutoDelete(True)
        self._qdrant = qdrant_manager
        self._text = query_text
        self._criteria = criteria or {}
        self.signals = ListingSearchWorkerSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        if self._cancelled:
            return
        try:
            self.signals.status.emit("Encoding query…")
            from backend.src.pipeline.vector_ingestion import get_or_load_model

            model = get_or_load_model()
            if self._cancelled:
                return

            output = model.encode(
                [self._text],
                max_length=128,
                return_dense=False,
                return_sparse=True,
                return_colbert_vecs=False,
            )
            sw = output["lexical_weights"][0]
            indices = [int(k) for k in sw.keys()]
            values = [float(v) for v in sw.values()]

            if self._cancelled:
                return

            self.signals.status.emit("Searching…")
            filt = (
                self._qdrant.build_filter(self._criteria) if self._criteria else None
            )
            results = self._qdrant.search_sparse(
                indices, values, filt=filt, limit=200
            )

            if not self._cancelled:
                self.signals.finished.emit([uid for uid, _ in results])
        except Exception as exc:
            logger.exception("[ListingSearchWorker] %s", exc)
            if not self._cancelled:
                self.signals.error.emit(str(exc))
