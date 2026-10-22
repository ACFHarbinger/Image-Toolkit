"""Setting key catalog (W0-16 / #880).

The preserved keys and scopes from ``gui/src/preferences/definitions.py``
— one catalog for both GUIs. Keys are never renamed here; a key change
lands in both catalogs in the same PR, which ``test_keys_catalog.py``
enforces by loading the Qt-free gui definitions module by path and
comparing.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .scopes import SettingScope


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


def _coerce_dict(val: Any, default: dict) -> dict:
    if isinstance(val, dict):
        return dict(val)
    if isinstance(val, str) and val:
        with contextlib.suppress(ValueError):
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else default
    return default


def _coerce_bytes(val: Any, default: bytes | None) -> bytes | None:
    if isinstance(val, bytes):
        return val
    if hasattr(val, "data"):
        return bytes(val.data())
    return default


@dataclass(frozen=True)
class SettingDefinition:
    """Specification and schema for a single setting key."""

    key: str
    scope: SettingScope
    default: Any
    value_type: Any
    description: str = ""
    validator: Optional[Callable[[Any], bool]] = None

    def cast(self, raw_value: Any) -> Any:
        """Coerce raw storage values into the expected typed representation."""
        if raw_value is None:
            return self.default
        if self.value_type is bool:
            return _coerce_bool(raw_value)
        if self.value_type is int:
            return _coerce_int(raw_value, self.default)
        if self.value_type is float:
            return _coerce_float(raw_value, self.default)
        if self.value_type is str:
            return str(raw_value)
        if self.value_type is list:
            return _coerce_list(raw_value, self.default)
        if self.value_type is dict:
            return _coerce_dict(raw_value, self.default)
        if self.value_type is bytes:
            return _coerce_bytes(raw_value, self.default)
        return raw_value

    def validate(self, value: Any) -> bool:
        """Check whether the value satisfies validation rules."""
        if self.validator is None:
            return True
        with contextlib.suppress(Exception):
            return bool(self.validator(value))
        return False


DEVICE = SettingScope.DEVICE
ACCOUNT = SettingScope.ACCOUNT


class SettingKeys:
    """Canonical registry of known application settings and their ownership."""

    MINIMIZE_TO_TRAY = SettingDefinition(
        key="preferences/minimize_to_tray",
        scope=DEVICE,
        default=False,
        value_type=bool,
        description="Close button minimizes MainWindow to system tray",
    )
    MAINWINDOW_GEOMETRY = SettingDefinition(
        key="mainwindow/geometry",
        scope=DEVICE,
        default=None,
        value_type=bytes,
        description="MainWindow restoreGeometry serialized payload (opaque to the service)",
    )
    POSTGRES_HOST = SettingDefinition(
        key="postgres/DB_HOST",
        scope=DEVICE,
        default="",
        value_type=str,
        description="PostgreSQL database host address",
    )
    POSTGRES_PORT = SettingDefinition(
        key="postgres/DB_PORT",
        scope=DEVICE,
        default="",
        value_type=str,
        description="PostgreSQL database port",
    )
    POSTGRES_NAME = SettingDefinition(
        key="postgres/DB_NAME",
        scope=DEVICE,
        default="",
        value_type=str,
        description="PostgreSQL database name",
    )
    POSTGRES_USER = SettingDefinition(
        key="postgres/DB_USER",
        scope=DEVICE,
        default="",
        value_type=str,
        description="PostgreSQL database username",
    )
    RECURSIVE_SCAN = SettingDefinition(
        key="preferences/recursive_scan",
        scope=ACCOUNT,
        default=True,
        value_type=bool,
        description="Scan subdirectories recursively in file explorers and galleries",
    )
    FAVOURITE_DIRECTORIES = SettingDefinition(
        key="preferences/favourite_directories",
        scope=ACCOUNT,
        default=[],
        value_type=list,
        description="List of pinned favourite directory paths",
    )
    MAL_FETCH_METHOD = SettingDefinition(
        key="preferences/mal_fetch_method",
        scope=ACCOUNT,
        default="jikan",
        value_type=str,
        description="MAL fetch client: 'jikan' | 'official_api' | 'scrape'",
    )
    THEME = SettingDefinition(
        key="theme",
        scope=ACCOUNT,
        default="dark",
        value_type=str,
        description="Active application theme name ('dark', 'light', etc.)",
    )
    CATEGORY_ACCENTS = SettingDefinition(
        key="preferences/category_accents",
        scope=ACCOUNT,
        default={},
        value_type=dict,
        description="Sparse per-category accent color hex overrides",
    )
    STARTUP_CATEGORY = SettingDefinition(
        key="preferences/startup_category",
        scope=ACCOUNT,
        default="System Tools",
        value_type=str,
        description="Default category tab opened at startup",
    )
    INITIAL_CACHE_MAXSIZE = SettingDefinition(
        key="preferences/initial_cache_maxsize",
        scope=ACCOUNT,
        default=300,
        value_type=int,
        description="Initial cache capacity limit",
    )
    RESTORE_LAST_DIR = SettingDefinition(
        key="preferences/restore_last_dir",
        scope=ACCOUNT,
        default=True,
        value_type=bool,
        description="Restore previous working directory on relaunch",
    )
    RESTORE_LAST_TAB = SettingDefinition(
        key="preferences/restore_last_tab",
        scope=ACCOUNT,
        default=False,
        value_type=bool,
        description="Restore previous active tab on relaunch",
    )
    DEFAULT_OPEN_DIR = SettingDefinition(
        key="preferences/default_open_dir",
        scope=ACCOUNT,
        default="",
        value_type=str,
        description="Default folder path opened when launching or browsing",
    )
    RECENT_DIRS_COUNT = SettingDefinition(
        key="preferences/recent_dirs_count",
        scope=ACCOUNT,
        default=10,
        value_type=int,
        description="Number of recent directory entries retained",
    )
    EXPERIMENTAL_STITCH_WORKSPACE = SettingDefinition(
        key="experimental/stitch_workspace",
        scope=ACCOUNT,
        default=False,
        value_type=bool,
        description="Enable the experimental Stitch workspace routes for this account",
    )
    EXPERIMENTAL_RUNTIME_SHELL = SettingDefinition(
        key="experimental/runtime_shell",
        scope=ACCOUNT,
        default=False,
        value_type=bool,
        description="Enable the experimental rail/ribbon runtime shell for this account",
    )
    EXPERIMENTAL_DL_WORKSPACE = SettingDefinition(
        key="experimental/dl_workspace",
        scope=ACCOUNT,
        default=False,
        value_type=bool,
        description="Enable the experimental Deep Learning workspace routes for this account",
    )
    DL_DISCLOSURE_TIER_TRAIN = SettingDefinition(
        key="dl/disclosure_tier_train",
        scope=ACCOUNT,
        default="standard",
        value_type=str,
        description="Progressive disclosure tier for Deep Learning Train destination",
    )
    DL_DISCLOSURE_TIER_GENERATE = SettingDefinition(
        key="dl/disclosure_tier_generate",
        scope=ACCOUNT,
        default="standard",
        value_type=str,
        description="Progressive disclosure tier for Deep Learning Generate destination",
    )
    DL_ONBOARDING_TRAIN_DISMISSED = SettingDefinition(
        key="dl/onboarding_train_dismissed",
        scope=ACCOUNT,
        default=False,
        value_type=bool,
        description="First-run Train onboarding card dismissed",
    )
    DL_ONBOARDING_GENERATE_DISMISSED = SettingDefinition(
        key="dl/onboarding_generate_dismissed",
        scope=ACCOUNT,
        default=False,
        value_type=bool,
        description="First-run Generate onboarding card dismissed",
    )
    DL_ONBOARDING_REVIEW_DISMISSED = SettingDefinition(
        key="dl/onboarding_review_dismissed",
        scope=ACCOUNT,
        default=False,
        value_type=bool,
        description="First-run Review onboarding card dismissed",
    )


KNOWN_DEFINITIONS: list[SettingDefinition] = [
    # key-for-key with gui/src/preferences/definitions.py's
    # ALL_KNOWN_DEFINITIONS (test_keys_catalog.py enforces parity);
    # CATEGORY_ACCENTS mirrors gui: defined on the keys class but not
    # listed in the shipped catalog there either.
    SettingKeys.MINIMIZE_TO_TRAY,
    SettingKeys.MAINWINDOW_GEOMETRY,
    SettingKeys.POSTGRES_HOST,
    SettingKeys.POSTGRES_PORT,
    SettingKeys.POSTGRES_NAME,
    SettingKeys.POSTGRES_USER,
    SettingKeys.RECURSIVE_SCAN,
    SettingKeys.FAVOURITE_DIRECTORIES,
    SettingKeys.MAL_FETCH_METHOD,
    SettingKeys.THEME,
    SettingKeys.STARTUP_CATEGORY,
    SettingKeys.INITIAL_CACHE_MAXSIZE,
    SettingKeys.RESTORE_LAST_DIR,
    SettingKeys.RESTORE_LAST_TAB,
    SettingKeys.DEFAULT_OPEN_DIR,
    SettingKeys.RECENT_DIRS_COUNT,
    SettingKeys.EXPERIMENTAL_STITCH_WORKSPACE,
    SettingKeys.EXPERIMENTAL_RUNTIME_SHELL,
    SettingKeys.EXPERIMENTAL_DL_WORKSPACE,
    SettingKeys.DL_DISCLOSURE_TIER_TRAIN,
    SettingKeys.DL_DISCLOSURE_TIER_GENERATE,
    SettingKeys.DL_ONBOARDING_TRAIN_DISMISSED,
    SettingKeys.DL_ONBOARDING_GENERATE_DISMISSED,
    SettingKeys.DL_ONBOARDING_REVIEW_DISMISSED,
]

_DEFINITIONS_BY_KEY: dict[str, SettingDefinition] = {d.key: d for d in KNOWN_DEFINITIONS}


def definition_for(key: str) -> Optional[SettingDefinition]:
    """Look up a known setting definition by key."""
    return _DEFINITIONS_BY_KEY.get(key)


def infer_scope(key: str) -> SettingScope:
    """Determine the ownership scope for a key string (heuristic mirror of
    the Qt store's ``infer_scope`` — known keys first, then namespaces)."""
    definition = _DEFINITIONS_BY_KEY.get(key)
    if definition is not None:
        return definition.scope

    if key.startswith(("session/", "splitters/", "splitter/", "labels/")):
        return SettingScope.SESSION

    if (
        key.startswith("preferences/")
        or key == "theme"
        or key.startswith("system_preference_profiles")
        or key.startswith("active_tab_configs")
    ):
        # Note: preferences/minimize_to_tray is explicitly registered as DEVICE
        return SettingScope.ACCOUNT

    return SettingScope.DEVICE


__all__ = [
    "KNOWN_DEFINITIONS",
    "SettingDefinition",
    "SettingKeys",
    "definition_for",
    "infer_scope",
]
