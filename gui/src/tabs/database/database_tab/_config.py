"""Tab-config persistence controller for ``DatabaseTab`` (§5.17, #544)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    pass


class DatabaseConfigController:
    """Tab-level config persistence hooks used by the profile system."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def collect(self) -> dict:
        return {"auto_open": self.tab.db is not None}

    def get_default_config(self) -> dict:
        return {"auto_open": True}

    def set_config(self, config: dict) -> None:
        tab = self.tab
        try:
            if config.get("auto_open", True) and tab.db is None:
                tab.connect_database(silent=True)
        except Exception as e:
            print(f"Error applying DatabaseTab config: {e}")
            QMessageBox.warning(
                tab, "Config Error", f"Failed to apply some settings: {e}"
            )


# Backward-compatible alias
_ConfigMixin = DatabaseConfigController

__all__ = ["DatabaseConfigController", "_ConfigMixin"]
