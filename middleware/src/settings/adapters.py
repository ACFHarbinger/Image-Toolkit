"""Per-scope settings stores (W0-16 / #880).

Pluggable storage per ownership scope, mirroring the Qt shell's adapter
pattern but Qt-free: JSON file for DEVICE, injectable for ACCOUNT (the
sealed vault adapter from #879 slots in without touching the service),
in-memory for SESSION. ``JsonFileStore`` writes atomically (temp file +
``os.replace``) so a crash never leaves a torn settings file.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Protocol

from .scopes import SettingScope

#: Tagged wrapper for bytes values inside JSON stores ("$bytes": hex).
_BYTES_TAG = "$bytes"


def encode_value(value: Any) -> Any:
    """Make a value JSON-serializable (bytes become a tagged wrapper)."""
    if isinstance(value, (bytes, bytearray)):
        return {_BYTES_TAG: bytes(value).hex()}
    return value


def decode_value(raw: Any) -> Any:
    """Undo :func:`encode_value` (tagged wrappers become bytes)."""
    if isinstance(raw, dict) and set(raw) == {_BYTES_TAG}:
        return bytes.fromhex(raw[_BYTES_TAG])
    return raw


class SettingsStore(Protocol):
    """Storage contract for one scope."""

    def get(self, key: str, default: Any = None) -> Any: ...

    def set(self, key: str, value: Any) -> None: ...

    def contains(self, key: str) -> bool: ...

    def remove(self, key: str) -> None: ...


class MemoryStore:
    """SESSION-scope store: ephemeral, discarded on exit."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._values[key] = encode_value(value)

    def contains(self, key: str) -> bool:
        return key in self._values

    def remove(self, key: str) -> None:
        self._values.pop(key, None)


class JsonFileStore:
    """Persistent store for one scope as a flat JSON document.

    The directory defaults to ``~/.image-toolkit/settings/`` with one file
    per scope (``device.json``, ``account.json``); tests pass their own
    ``tmp_path``. Writes are atomic: the document is serialized to a temp
    file in the same directory and renamed onto the target.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._document: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._document is None:
            if self.path.is_file():
                self._document = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                self._document = {}
        return self._document

    def _flush(self) -> None:
        document = self._load()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(document, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp_name, self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    def get(self, key: str, default: Any = None) -> Any:
        return decode_value(self._load().get(key, default))

    def set(self, key: str, value: Any) -> None:
        document = self._load()
        document[key] = encode_value(value)
        self._flush()

    def contains(self, key: str) -> bool:
        return key in self._load()

    def remove(self, key: str) -> None:
        document = self._load()
        if key in document:
            del document[key]
            self._flush()

    def keys(self) -> list[str]:
        return sorted(self._load())


def default_store(scope: SettingScope, base_dir: str | Path | None = None) -> SettingsStore:
    """The default store for a scope."""
    if scope is SettingScope.SESSION:
        return MemoryStore()
    base = Path(base_dir) if base_dir is not None else (Path.home() / ".image-toolkit" / "settings")
    return JsonFileStore(base / f"{scope.value}.json")


__all__ = [
    "JsonFileStore",
    "MemoryStore",
    "SettingsStore",
    "decode_value",
    "default_store",
    "encode_value",
]
