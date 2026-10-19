"""Live tail of a training run's events.jsonl (#741, consumed by #742).

Discipline (per the issue): all reading happens on a worker thread — the
QFileSystemWatcher only schedules a read; the GUI thread never touches
the file. Only complete lines advance the offset, so a half-written tail
line from a live append is picked up on the next change.
"""
from __future__ import annotations

from pathlib import Path

from middleware.src.core.training_runs import EVENTS_FILE_NAME
from PySide6.QtCore import QFileSystemWatcher, QObject, Signal, Slot

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.worker_retention import retain_until_stopped


class _TailRead(BaseQThreadWorker):
    def __init__(self, path: Path, offset: int) -> None:
        super().__init__()
        self._path = path
        self._offset = offset

    def _execute(self) -> object:
        import json

        events: list[dict] = []
        if not self._path.is_file():
            return (self._offset, events)
        with open(self._path, "rb") as fh:
            fh.seek(self._offset)
            data = fh.read()
        end = data.rfind(b"\n")
        if end < 0:
            return (self._offset, events)  # no complete line yet
        for line in data[:end].splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(event, dict):
                events.append(event)
        return (self._offset + len(data[: end + 1]), events)


class TrainingEventTail(QObject):
    """Emits parsed events as they are appended to a run's events.jsonl."""

    events = Signal(list)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._run_dir: Path | None = None
        self._offset = 0
        self._busy = False
        self._generation = 0
        self._worker = None
        self._dirty = False
        self._stopped = False
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_changed)
        self._watcher.fileChanged.connect(self._on_changed)

    def start(self, run_dir: str | Path) -> None:
        self.stop()
        self._stopped = False
        self._run_dir = Path(run_dir)
        self._offset = 0
        self._watcher.addPath(str(self._run_dir))
        self._on_changed()

    def stop(self) -> None:
        self._stopped = True
        self._generation += 1
        for path in self._watcher.directories() + self._watcher.files():
            self._watcher.removePath(path)
        self._run_dir = None

    @Slot()
    @Slot(str)
    def _on_changed(self, *_args) -> None:
        if self._stopped or self._run_dir is None:
            return
        if self._busy:
            self._dirty = True
            return
        events_file = self._run_dir / EVENTS_FILE_NAME
        fpath = str(events_file)
        if events_file.is_file() and fpath not in self._watcher.files():
            self._watcher.addPath(fpath)
        self._busy = True
        self._dirty = False
        worker = _TailRead(events_file, self._offset)
        worker.generation = self._generation
        self._worker = worker
        worker.finished.connect(self._on_read)
        worker.error.connect(self._on_error)
        retain_until_stopped(worker)
        worker.start()

    @Slot(object)
    def _on_read(self, payload: object) -> None:
        self._busy = False
        worker = self.sender()
        if worker is not None and worker.generation != self._generation:
            self._on_changed()
            return
        if self._stopped or not isinstance(payload, tuple):
            return
        offset, events = payload
        advanced = offset != self._offset
        self._offset = offset
        if events:
            self.events.emit(events)
        # QFileSystemWatcher can coalesce rapid fileChanged events; re-read
        # only when the last read actually advanced, so an idle file never
        # spins a worker loop.
        if advanced or self._dirty:
            self._on_changed()

    @Slot(object)
    def _on_error(self, exc: object) -> None:
        self._busy = False
        if not self._stopped:
            self.error.emit(str(exc))
