"""gui/src/preferences/definitions.py
===================================
Typed preference definitions and canonical key catalog (§1.1, #525).
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, TypeVar

from .scopes import PreferenceScope

T = TypeVar("T")


def _coerce_bool(val: Any) -> bool:
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "on")
    return bool(val)


def _coerce_int(val: Any, default: int) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _coerce_float(val: Any, default: float) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _coerce_list(val: Any, default: list) -> list:
    if isinstance(val, (list, tuple)):
        return list(val)
    if isinstance(val, str):
        return [val] if val else []
    return default


def _coerce_bytes(val: Any, default: bytes | None) -> bytes | None:
    if isinstance(val, bytes):
        return val
    if hasattr(val, "data"):
        return bytes(val.data())
    return default


@dataclass(frozen=True)
class PreferenceDefinition(Generic[T]):
    """Specification and schema for a single preference key."""

    key: str
    scope: PreferenceScope
    default: T
    value_type: type[T]
    description: str = ""
    validator: Optional[Callable[[T], bool]] = None

    def cast(self, raw_value: Any) -> T:
        """Coerce raw storage values into the expected typed representation."""
        if raw_value is None:
            return self.default
        if self.value_type is bool:
            return _coerce_bool(raw_value)  # type: ignore
        if self.value_type is int:
            return _coerce_int(raw_value, self.default)  # type: ignore
        if self.value_type is float:
            return _coerce_float(raw_value, self.default)  # type: ignore
        if self.value_type is str:
            return str(raw_value)  # type: ignore
        if self.value_type is list:
            return _coerce_list(raw_value, self.default)  # type: ignore
        if self.value_type is dict:
            return raw_value if isinstance(raw_value, dict) else self.default  # type: ignore
        if self.value_type is bytes:
            return _coerce_bytes(raw_value, self.default)  # type: ignore
        return raw_value  # type: ignore

    def validate(self, value: T) -> bool:
        """Check whether the value satisfies validation rules."""
        if self.validator is None:
            return True
        with contextlib.suppress(Exception):
            return bool(self.validator(value))
        return False


class PrefKeys:
    """Canonical registry of known application preferences and their ownership."""

    # ── Device Scoped (QSettings / local hardware & window layout) ───────────
    MINIMIZE_TO_TRAY = PreferenceDefinition(
        key="preferences/minimize_to_tray",
        scope=PreferenceScope.DEVICE,
        default=False,
        value_type=bool,
        description="Close button minimizes MainWindow to system tray",
    )
    MAINWINDOW_GEOMETRY = PreferenceDefinition(
        key="mainwindow/geometry",
        scope=PreferenceScope.DEVICE,
        default=None,
        value_type=bytes,
        description="MainWindow restoreGeometry serialized bytes",
    )
    POSTGRES_HOST = PreferenceDefinition(
        key="postgres/DB_HOST",
        scope=PreferenceScope.DEVICE,
        default="",
        value_type=str,
        description="PostgreSQL database host address",
    )
    POSTGRES_PORT = PreferenceDefinition(
        key="postgres/DB_PORT",
        scope=PreferenceScope.DEVICE,
        default="",
        value_type=str,
        description="PostgreSQL database port",
    )
    POSTGRES_NAME = PreferenceDefinition(
        key="postgres/DB_NAME",
        scope=PreferenceScope.DEVICE,
        default="",
        value_type=str,
        description="PostgreSQL database name",
    )
    POSTGRES_USER = PreferenceDefinition(
        key="postgres/DB_USER",
        scope=PreferenceScope.DEVICE,
        default="",
        value_type=str,
        description="PostgreSQL database username",
    )

    # ── Account Scoped (Vault credentials / user profile) ────────────────────
    RECURSIVE_SCAN = PreferenceDefinition(
        key="preferences/recursive_scan",
        scope=PreferenceScope.ACCOUNT,
        default=True,
        value_type=bool,
        description="Scan subdirectories recursively in file explorers and galleries",
    )
    FAVOURITE_DIRECTORIES = PreferenceDefinition(
        key="preferences/favourite_directories",
        scope=PreferenceScope.ACCOUNT,
        default=[],
        value_type=list,
        description="List of pinned favourite directory paths",
    )
    MAL_FETCH_METHOD = PreferenceDefinition(
        key="preferences/mal_fetch_method",
        scope=PreferenceScope.ACCOUNT,
        default="jikan",
        value_type=str,
        description="MAL fetch client: 'jikan' | 'official_api' | 'scrape'",
    )
    THEME = PreferenceDefinition(
        key="theme",
        scope=PreferenceScope.ACCOUNT,
        default="dark",
        value_type=str,
        description="Active application theme name ('dark', 'light', etc.)",
    )
    STARTUP_CATEGORY = PreferenceDefinition(
        key="preferences/startup_category",
        scope=PreferenceScope.ACCOUNT,
        default="System Tools",
        value_type=str,
        description="Default category tab opened at startup",
    )
    INITIAL_CACHE_MAXSIZE = PreferenceDefinition(
        key="preferences/initial_cache_maxsize",
        scope=PreferenceScope.ACCOUNT,
        default=300,
        value_type=int,
        description="Initial cache capacity limit",
    )
    RESTORE_LAST_DIR = PreferenceDefinition(
        key="preferences/restore_last_dir",
        scope=PreferenceScope.ACCOUNT,
        default=True,
        value_type=bool,
        description="Restore previous working directory on relaunch",
    )
    RESTORE_LAST_TAB = PreferenceDefinition(
        key="preferences/restore_last_tab",
        scope=PreferenceScope.ACCOUNT,
        default=False,
        value_type=bool,
        description="Restore previous active tab on relaunch",
    )
    DEFAULT_OPEN_DIR = PreferenceDefinition(
        key="preferences/default_open_dir",
        scope=PreferenceScope.ACCOUNT,
        default="",
        value_type=str,
        description="Default folder path opened when launching or browsing",
    )
    RECENT_DIRS_COUNT = PreferenceDefinition(
        key="preferences/recent_dirs_count",
        scope=PreferenceScope.ACCOUNT,
        default=10,
        value_type=int,
        description="Number of recent directory entries retained",
    )
    EXPERIMENTAL_STITCH_WORKSPACE = PreferenceDefinition(
        key="experimental/stitch_workspace",
        scope=PreferenceScope.ACCOUNT,
        default=False,
        value_type=bool,
        description="Enable the experimental Stitch workspace routes for this account",
    )


ALL_KNOWN_DEFINITIONS: list[PreferenceDefinition] = [
    PrefKeys.MINIMIZE_TO_TRAY,
    PrefKeys.MAINWINDOW_GEOMETRY,
    PrefKeys.POSTGRES_HOST,
    PrefKeys.POSTGRES_PORT,
    PrefKeys.POSTGRES_NAME,
    PrefKeys.POSTGRES_USER,
    PrefKeys.RECURSIVE_SCAN,
    PrefKeys.FAVOURITE_DIRECTORIES,
    PrefKeys.MAL_FETCH_METHOD,
    PrefKeys.THEME,
    PrefKeys.STARTUP_CATEGORY,
    PrefKeys.INITIAL_CACHE_MAXSIZE,
    PrefKeys.RESTORE_LAST_DIR,
    PrefKeys.RESTORE_LAST_TAB,
    PrefKeys.DEFAULT_OPEN_DIR,
    PrefKeys.RECENT_DIRS_COUNT,
    PrefKeys.EXPERIMENTAL_STITCH_WORKSPACE,
]

__all__ = [
    "ALL_KNOWN_DEFINITIONS",
    "PrefKeys",
    "PreferenceDefinition",
]
