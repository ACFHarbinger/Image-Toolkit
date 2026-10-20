"""Qt-free shell metadata shared by the PySide6 and Tauri desktops."""

from middleware.src.shell.catalog import (
    CatalogAlias,
    CatalogEntry,
    CatalogWindow,
    ModuleCategory,
    shell_catalog,
)
from middleware.src.shell.window_roles import (
    hide_on_close_labels,
    popout_ids,
    request_stop_cloud,
    windows,
)

__all__ = [
    "CatalogAlias",
    "CatalogEntry",
    "CatalogWindow",
    "ModuleCategory",
    "hide_on_close_labels",
    "popout_ids",
    "request_stop_cloud",
    "shell_catalog",
    "windows",
]
