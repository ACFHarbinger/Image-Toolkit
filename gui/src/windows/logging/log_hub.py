"""
Central Log Hub & Python Logging Integration (§2.17).
=====================================================
Thread-safe centralized logging hub and activity history dispatcher.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import QObject, Signal, Slot


@dataclass(frozen=True)
class LogEntry:
    """Individual structured log entry."""

    timestamp: str
    level: str
    source: str
    message: str

    @property
    def level_order(self) -> int:
        levels = {
            "DEBUG": 10,
            "INFO": 20,
            "SUCCESS": 25,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50,
        }
        return levels.get(self.level.upper(), 20)

    def formatted_line(self) -> str:
        return f"[{self.timestamp}] [{self.level.upper():<7}] [{self.source}] {self.message}"


class LogHub(QObject):
    """
    Central application log dispatcher and activity history store.

    Signals
    -------
    entry_added(LogEntry)
        Emitted on GUI thread when a new log entry is recorded.
    cleared()
        Emitted when logs are cleared.
    """

    entry_added = Signal(object)
    cleared = Signal()
    _request_log = Signal(str, str, str)

    _instance: Optional[LogHub] = None

    def __init__(self, max_entries: int = 2000, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._max_entries = max_entries
        self._entries: List[LogEntry] = []
        self._error_count = 0
        self._warning_count = 0
        self._request_log.connect(self.log)


    @classmethod
    def instance(cls) -> LogHub:
        if cls._instance is None:
            cls._instance = LogHub()
        return cls._instance

    @classmethod
    def reset_instance_for_testing(cls) -> None:
        cls._instance = None

    # ---- Logging methods ------------------------------------------------

    @Slot(str, str, str)
    def log(self, level: str, message: str, source: str = "general") -> None:
        """Add a log entry. Thread-safe."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = LogEntry(
            timestamp=timestamp,
            level=level.upper(),
            source=source,
            message=message,
        )

        if entry.level in ("ERROR", "CRITICAL"):
            self._error_count += 1
        elif entry.level == "WARNING":
            self._warning_count += 1

        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            removed = self._entries.pop(0)
            if removed.level in ("ERROR", "CRITICAL"):
                self._error_count = max(0, self._error_count - 1)
            elif removed.level == "WARNING":
                self._warning_count = max(0, self._warning_count - 1)

        self.entry_added.emit(entry)

    def debug(self, message: str, source: str = "general") -> None:
        self.log("DEBUG", message, source)

    def info(self, message: str, source: str = "general") -> None:
        self.log("INFO", message, source)

    def success(self, message: str, source: str = "general") -> None:
        self.log("SUCCESS", message, source)

    def warning(self, message: str, source: str = "general") -> None:
        self.log("WARNING", message, source)

    def error(self, message: str, source: str = "general") -> None:
        self.log("ERROR", message, source)

    def critical(self, message: str, source: str = "general") -> None:
        self.log("CRITICAL", message, source)

    # ---- Querying -------------------------------------------------------

    def entries(self) -> List[LogEntry]:
        return list(self._entries)

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def warning_count(self) -> int:
        return self._warning_count

    @Slot()
    def clear(self) -> None:
        self._entries.clear()
        self._error_count = 0
        self._warning_count = 0
        self.cleared.emit()


class UnifiedLogHandler(logging.Handler):
    """Python standard logging.Handler forwarding records to LogHub."""

    def __init__(self, hub: Optional[LogHub] = None, source: Optional[str] = None) -> None:
        super().__init__()
        self.hub = hub or LogHub.instance()
        self.source_override = source

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            source = self.source_override or record.name
            level = record.levelname
            # Thread-safe dispatch via Qt Signal
            self.hub._request_log.emit(level, msg, source)
        except Exception:
            self.handleError(record)



def get_log_hub() -> LogHub:
    """Convenience accessor for global singleton LogHub."""
    return LogHub.instance()


__all__ = ["LogEntry", "LogHub", "UnifiedLogHandler", "get_log_hub"]
