"""gui/src/preferences/store.py
============================
Central PreferenceStore facade with typed key ownership and pluggable adapters (§1.1, #525).
"""

from __future__ import annotations

import contextlib
from threading import RLock
from typing import Any, Callable, Optional, TypeVar

from .adapters.base import PreferenceAdapter
from .adapters.memory_adapter import MemoryPreferenceAdapter
from .adapters.qsettings_adapter import QSettingsPreferenceAdapter
from .adapters.vault_adapter import VaultPreferenceAdapter
from .definitions import ALL_KNOWN_DEFINITIONS, PreferenceDefinition, PrefKeys
from .scopes import PreferenceScope

T = TypeVar("T")
ChangeCallback = Callable[[str, Any, PreferenceScope], None]


class PreferenceStore:
    """Canonical gateway for all application preferences.

    Enforces single-source-of-truth semantics by routing every read/write to
    its designated ownership scope (DEVICE, ACCOUNT, SESSION).
    """

    _global_instance: Optional[PreferenceStore] = None
    _singleton_lock: RLock = RLock()

    def __init__(self, lazy_adapters: bool = False) -> None:
        self._lock = RLock()
        self._adapters: dict[PreferenceScope, PreferenceAdapter] = {}
        self._definitions: dict[str, PreferenceDefinition] = {}
        self._subscribers: list[ChangeCallback] = []

        # Register standard catalog
        for definition in ALL_KNOWN_DEFINITIONS:
            self.register_definition(definition)

        if not lazy_adapters:
            self.setup_default_adapters()

    def setup_default_adapters(self) -> None:
        """Initialize standard default adapters for the three scopes."""
        with self._lock:
            if PreferenceScope.DEVICE not in self._adapters:
                self._adapters[PreferenceScope.DEVICE] = QSettingsPreferenceAdapter()
            if PreferenceScope.ACCOUNT not in self._adapters:
                self._adapters[PreferenceScope.ACCOUNT] = VaultPreferenceAdapter()
            if PreferenceScope.SESSION not in self._adapters:
                self._adapters[PreferenceScope.SESSION] = MemoryPreferenceAdapter()

    @classmethod
    def instance(cls) -> PreferenceStore:
        """Return global shared singleton instance."""
        with cls._singleton_lock:
            if cls._global_instance is None:
                cls._global_instance = cls()
            return cls._global_instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for test isolation)."""
        with cls._singleton_lock:
            cls._global_instance = None

    # ── Adapter management ────────────────────────────────────────────────────

    def register_adapter(self, scope: PreferenceScope, adapter: PreferenceAdapter) -> None:
        """Attach a custom adapter to a specific scope."""
        with self._lock:
            self._adapters[scope] = adapter

    def get_adapter(self, scope: PreferenceScope) -> PreferenceAdapter:
        """Retrieve the adapter currently attached to a scope."""
        with self._lock:
            if scope not in self._adapters:
                if scope == PreferenceScope.SESSION:
                    self._adapters[scope] = MemoryPreferenceAdapter()
                elif scope == PreferenceScope.ACCOUNT:
                    self._adapters[scope] = VaultPreferenceAdapter()
                else:
                    self._adapters[scope] = QSettingsPreferenceAdapter()
            return self._adapters[scope]

    def attach_vault_credentials(
        self,
        credentials: dict[str, Any],
        vault_manager: Any = None,
        account_name: str = "",
    ) -> None:
        """Attach user account credentials and vault manager to the ACCOUNT scope."""
        with self._lock:
            adapter = self.get_adapter(PreferenceScope.ACCOUNT)
            if isinstance(adapter, VaultPreferenceAdapter):
                adapter.set_credentials(credentials, vault_manager, account_name)
            else:
                self._adapters[PreferenceScope.ACCOUNT] = VaultPreferenceAdapter(
                    credentials=credentials,
                    vault_manager=vault_manager,
                    account_name=account_name,
                )

    # ── Definition management ─────────────────────────────────────────────────

    def register_definition(self, definition: PreferenceDefinition) -> None:
        """Register a known typed preference definition."""
        with self._lock:
            self._definitions[definition.key] = definition

    def get_definition(self, key: str) -> Optional[PreferenceDefinition]:
        """Look up a preference definition by its key."""
        with self._lock:
            return self._definitions.get(key)

    def infer_scope(self, key: str) -> PreferenceScope:
        """Determine ownership scope for a given key string."""
        with self._lock:
            defn = self._definitions.get(key)
            if defn is not None:
                return defn.scope

            # Namespace heuristic for dynamic keys
            if (
                key.startswith("session/")
                or key.startswith("splitters/")
                or key.startswith("splitter/")
                or key.startswith("labels/")
            ):
                return PreferenceScope.SESSION

            if (
                key.startswith("preferences/")
                or key == "theme"
                or key.startswith("system_preference_profiles")
                or key.startswith("active_tab_configs")
            ):
                # Note: preferences/minimize_to_tray is explicitly registered as DEVICE
                return PreferenceScope.ACCOUNT

            if (
                key.startswith("mainwindow/")
                or key.startswith("postgres/")
                or key.startswith("device/")
            ):
                return PreferenceScope.DEVICE

            return PreferenceScope.DEVICE

    # ── Read / Write operations ───────────────────────────────────────────────

    def get(self, key_or_def: str | PreferenceDefinition[T], default: Any = None) -> Any:
        """Read a preference value, applying type coercion and default rules."""
        with self._lock:
            if isinstance(key_or_def, PreferenceDefinition):
                defn = key_or_def
                key = defn.key
                scope = defn.scope
                eff_default = defn.default if default is None else default
            else:
                key = str(key_or_def)
                defn = self._definitions.get(key)
                if defn is not None:
                    scope = defn.scope
                    eff_default = defn.default if default is None else default
                else:
                    scope = self.infer_scope(key)
                    eff_default = default

            adapter = self.get_adapter(scope)
            if not adapter.contains(key):
                return eff_default

            raw_value = adapter.get(key, eff_default)
            if defn is not None:
                return defn.cast(raw_value)
            return raw_value

    def set(self, key_or_def: str | PreferenceDefinition[T], value: Any) -> None:
        """Store a preference value in its designated scope adapter."""
        with self._lock:
            if isinstance(key_or_def, PreferenceDefinition):
                defn = key_or_def
                key = defn.key
                scope = defn.scope
            else:
                key = str(key_or_def)
                defn = self._definitions.get(key)
                scope = defn.scope if defn is not None else self.infer_scope(key)

            if defn is not None:
                cast_value = defn.cast(value)
                if not defn.validate(cast_value):
                    raise ValueError(f"Value {value!r} failed validation for preference key '{key}'")
                value = cast_value

            adapter = self.get_adapter(scope)
            adapter.set(key, value)
            subscribers = list(self._subscribers)

        # Notify subscribers outside the lock to avoid deadlocks
        for callback in subscribers:
            with contextlib.suppress(Exception):
                callback(key, value, scope)

    def contains(self, key_or_def: str | PreferenceDefinition[T]) -> bool:
        """Check whether a preference is present in its scope adapter."""
        with self._lock:
            if isinstance(key_or_def, PreferenceDefinition):
                key = key_or_def.key
                scope = key_or_def.scope
            else:
                key = str(key_or_def)
                defn = self._definitions.get(key)
                scope = defn.scope if defn is not None else self.infer_scope(key)

            return self.get_adapter(scope).contains(key)

    def remove(self, key_or_def: str | PreferenceDefinition[T]) -> None:
        """Delete a preference from its scope adapter."""
        with self._lock:
            if isinstance(key_or_def, PreferenceDefinition):
                key = key_or_def.key
                scope = key_or_def.scope
            else:
                key = str(key_or_def)
                defn = self._definitions.get(key)
                scope = defn.scope if defn is not None else self.infer_scope(key)

            self.get_adapter(scope).remove(key)

    def subscribe(self, callback: ChangeCallback) -> Callable[[], None]:
        """Subscribe to preference change notifications."""
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe


__all__ = [
    "ChangeCallback",
    "PrefKeys",
    "PreferenceDefinition",
    "PreferenceScope",
    "PreferenceStore",
]
