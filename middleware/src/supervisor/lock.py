"""Exclusive flock per data-dir role (supervisor or GUI)."""

from __future__ import annotations

from pathlib import Path

from filelock import FileLock, Timeout


class DataDirLock:
    """Hold an exclusive lock file under ``data_dir`` for the process lifetime."""

    def __init__(self, data_dir: Path, name: str) -> None:
        self.data_dir = data_dir
        self.name = name
        self.path = data_dir / f"{name}.lock"
        self._lock = FileLock(str(self.path), timeout=0)

    def acquire(self) -> bool:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._lock.acquire()
        except Timeout:
            return False
        return True

    def release(self) -> None:
        if self._lock.is_locked:
            self._lock.release()

    def __enter__(self) -> DataDirLock:
        if not self.acquire():
            raise Timeout(str(self.path))
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()
