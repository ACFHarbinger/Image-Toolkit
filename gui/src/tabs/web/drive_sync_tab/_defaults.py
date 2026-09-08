"""Loads the default auth/path field values into the UI.

Extracted from ``drive_sync_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import backend.src.constants as udef

from ._tab_bound import TabBoundController


class DriveSyncDefaultsController(TabBoundController):
    """Populates the config fields with their default values."""

    def load_configuration_defaults(self):
        self.key_file_path.setText(udef.SERVICE_ACCOUNT_FILE)
        self.client_secrets_path.setText(udef.CLIENT_SECRETS_FILE)
        self.token_file_path.setText(udef.TOKEN_FILE)
        self.local_path.setText(udef.LOCAL_SOURCE_PATH)
        self.remote_path.setText(udef.DRIVE_DESTINATION_FOLDER_NAME)
        self.share_email_input.setText("")


_DefaultsMixin = DriveSyncDefaultsController  # COMPAT(ui-arch-23): remove after callers drop the mixin name

__all__ = ["DriveSyncDefaultsController", "_DefaultsMixin"]
