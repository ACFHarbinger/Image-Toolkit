"""The one settings service shared by both GUIs (W0-16 / #880).

Qt-free counterpart of ``gui/src/preferences/store.py``: every read/write
routes to the key's ownership scope (DEVICE / ACCOUNT / SESSION) with the
same keys, defaults and coercion rules. The Qt shell keeps its
``PreferenceStore`` and can delegate here; the Tauri shell reaches it
over the bridge. Conflict detection is built in: concurrent writers are
caught by the compare-and-swap ``set_if_unchanged`` (raises
:class:`~middleware.src.settings.conflicts.ConflictError`), and legacy
migration overlap is reported per key
(:mod:`middleware.src.settings.migration`).

Session helpers mirror ``gui/src/preferences/session_values.py`` — same
``session/{class_name}/{key}`` scheme — minus the QSettings dependency.
"""

from __future__ import annotations

import contextlib
from threading import RLock
from typing import Any, Callable, Optional

from .adapters import SettingsStore, default_store
from .conflicts import ConflictError
from .keys import SettingDefinition, definition_for, infer_scope
from .scopes import SettingScope

ChangeCallback = Callable[[str, Any, SettingScope], None]


class SettingsService:
    """Scope-routed gateway for all application settings."""

    def __init__(self, stores: Optional[dict[SettingScope, SettingsStore]] = None) -> None:
        self._lock = RLock()
        self._stores: dict[SettingScope, SettingsStore] = dict(stores or {})
        self._subscribers: list[ChangeCallback] = []

    def store_for(self, scope: SettingScope) -> SettingsStore:
        """The store attached to a scope (created on first use)."""
        with self._lock:
            store = self._stores.get(scope)
            if store is None:
                store = default_store(scope)
                self._stores[scope] = store
            return store

    def attach_store(self, scope: SettingScope, store: SettingsStore) -> None:
        """Swap the store for a scope (e.g. the vault adapter for ACCOUNT)."""
        with self._lock:
            self._stores[scope] = store

    # ── Read / write ────────────────────────────────────────────────────────

    def definition(self, key: str) -> Optional[SettingDefinition]:
        return definition_for(key)

    def scope_of(self, key: str) -> SettingScope:
        return infer_scope(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Read a setting: definition default when absent, cast on the way out."""
        with self._lock:
            definition = definition_for(key)
            effective_default = default
            if definition is not None and default is None:
                effective_default = definition.default
            raw = self.store_for(self.scope_of(key)).get(key, effective_default)
            if definition is None:
                return raw
            return definition.cast(raw)

    def _prepare(self, key: str, value: Any) -> Any:
        """Cast and validate a value against its definition, if any."""
        definition = definition_for(key)
        if definition is None:
            return value
        cast_value = definition.cast(value)
        if not definition.validate(cast_value):
            raise ValueError(f"Value {value!r} failed validation for setting key '{key}'")
        return cast_value

    def set(self, key: str, value: Any) -> None:
        """Validate and store a setting in its scope; notify subscribers."""
        value = self._prepare(key, value)
        scope = self.scope_of(key)
        with self._lock:
            self.store_for(scope).set(key, value)
            subscribers = list(self._subscribers)
        for callback in subscribers:
            with contextlib.suppress(Exception):
                callback(key, value, scope)

    def set_if_unchanged(self, key: str, expected: Any, value: Any) -> None:
        """Compare-and-swap write; detects a concurrent writer.

        Fails with :class:`ConflictError` when the stored value differs
        from ``expected`` instead of silently overwriting it. The CAS
        decision and the write share one lock so a racing ``set`` cannot
        interleave.
        """
        value = self._prepare(key, value)
        scope = self.scope_of(key)
        with self._lock:
            current = self.get(key)
            if current != expected:
                raise ConflictError(key, expected=expected, actual=current)
            self.store_for(scope).set(key, value)
            subscribers = list(self._subscribers)
        for callback in subscribers:
            with contextlib.suppress(Exception):
                callback(key, value, scope)

    def contains(self, key: str) -> bool:
        with self._lock:
            return self.store_for(self.scope_of(key)).contains(key)

    def remove(self, key: str) -> None:
        with self._lock:
            self.store_for(self.scope_of(key)).remove(key)

    def subscribe(self, callback: ChangeCallback) -> Callable[[], None]:
        """Subscribe to change notifications; returns an unsubscribe."""
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    # ── Session values (gui/src/preferences/session_values.py scheme) ──────

    def session_value(self, class_name: str, key: str, default: Any = None) -> Any:
        return self.get(f"session/{class_name}/{key}", default)

    def set_session_value(self, class_name: str, key: str, value: Any) -> None:
        self.set(f"session/{class_name}/{key}", value)


__all__ = ["ChangeCallback", "SettingsService"]
