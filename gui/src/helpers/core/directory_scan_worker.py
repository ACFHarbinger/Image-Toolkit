"""Directory scan worker (ui-arch-39 / #561, R1.6).

``DirectoryScanWorker`` runs a :class:`ScanRequest` off the GUI thread on
the R1.1 worker base: :meth:`_execute` returns the collected path list
(``None`` on cancel), delivered via ``finished``; failures additionally
emit ``error`` with the exception object. No ``run()`` override, no
legacy signal names (see ``backend/validation/check_worker_base.py``).
"""

from __future__ import annotations

from PySide6.QtCore import Signal

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.services.directory_scan_service import (
    ScanRequest,
    collect_files,
)


class DirectoryScanWorker(BaseQThreadWorker):
    """Cancellable directory-scan worker for GUI scan slots."""

    finished = Signal(object)  # list[str] | None (None on cancel/failure)

    def __init__(self, request: ScanRequest) -> None:
        super().__init__()
        self._request = request

    @property
    def request(self) -> ScanRequest:
        """The scan request this worker executes."""
        return self._request

    def _execute(self) -> object:
        if self._cancelled:
            return None

        def is_cancelled() -> bool:
            return self._cancelled or self.isInterruptionRequested()

        def _on_progress(matched: int) -> None:
            self.progress.emit(matched, matched)

        paths = collect_files(
            self._request,
            is_cancelled=is_cancelled,
            on_progress=_on_progress,
        )
        if self._cancelled or self.isInterruptionRequested():
            return None
        return paths


__all__ = ["DirectoryScanWorker"]
