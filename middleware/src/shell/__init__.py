"""Qt-free shell metadata shared by the PySide6 and Tauri desktops."""

from middleware.src.shell.catalog import (
    CatalogAlias,
    CatalogEntry,
    CatalogWindow,
    ModuleCategory,
    shell_catalog,
)

__all__ = [
    "CatalogAlias",
    "CatalogEntry",
    "CatalogWindow",
    "ModuleCategory",
    "shell_catalog",
]
