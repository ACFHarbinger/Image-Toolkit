"""Tab-config persistence (``collect``/``get_default_config``/``set_config``).

Extracted from ``database_tab.py`` -- pure code motion, no logic change
(see ``_ui_connection.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox


class _ConfigMixin:
    """Tab-level config persistence hooks used by the profile system."""

    def collect(self) -> dict:
        # The unified library needs no connection settings (and the old
        # format's stored db_password was a security wart — deliberately
        # not emitted anymore).
        return {"auto_open": self.db is not None}

    def get_default_config(self) -> dict:
        return {"auto_open": True}

    def set_config(self, config: dict):
        try:
            # Legacy configs carried Postgres credentials — ignored now.
            if config.get("auto_open", True) and self.db is None:
                self.connect_database(silent=True)
        except Exception as e:
            print(f"Error applying DatabaseTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )


__all__ = ["_ConfigMixin"]
