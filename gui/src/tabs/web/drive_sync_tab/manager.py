"""``DriveSyncTab`` -- composed controllers over ``QWidget`` (#544)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtWidgets import QLineEdit, QWidget

from ....windows.logging import LogWindow
from ._auth_config import DriveSyncAuthController
from ._browsers import DriveSyncBrowsersController
from ._config import DriveSyncConfigController
from ._defaults import DriveSyncDefaultsController
from ._provider_switch import DriveSyncProviderController
from ._remote_map import DriveSyncRemoteMapController
from ._share_folder import DriveSyncShareFolderController
from ._sync_worker import DriveSyncSyncWorkerController
from ._ui_builder import DriveSyncUIBuilder
from ._ui_lock import DriveSyncUILockController


class DriveSyncTab(QWidget):
    """GUI tab for Cloud Drive one-way sync (QRunnable + QThreadPool).

    Phase 2 (ui-arch-23/#544): mixins collapsed into composed controllers.
    """

    # --- QML Integration ---
    qml_settings_changed = Signal()
    qml_log_changed = Signal()
    qml_progress_changed = Signal()

    def __init__(self, vault_manager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vault_manager = vault_manager
        self.current_worker: Optional[Any] = None

        # QML Integration
        self._overwrite = False
        self._verify_integrity = False
        self._log_text = ""
        self._progress_value = 0.0

        self.log_window = LogWindow(parent=self)

        self.ui_builder = DriveSyncUIBuilder(self)
        self.provider_controller = DriveSyncProviderController(self)
        self.auth_controller = DriveSyncAuthController(self)
        self.defaults_controller = DriveSyncDefaultsController(self)
        self.remote_map_controller = DriveSyncRemoteMapController(self)
        self.share_folder_controller = DriveSyncShareFolderController(self)
        self.sync_worker_controller = DriveSyncSyncWorkerController(self)
        self.ui_lock_controller = DriveSyncUILockController(self)
        self.browsers_controller = DriveSyncBrowsersController(self)
        self.config_controller = DriveSyncConfigController(self)

        self.ui_builder._build_ui()

    # ------------------------------------------------------------------
    # Auth facade
    # ------------------------------------------------------------------
    def _build_auth_config(self) -> Optional[Dict[str, Any]]:
        return self.auth_controller._build_auth_config()

    # ------------------------------------------------------------------
    # Browsers facade
    # ------------------------------------------------------------------
    def browse_key_file(self):
        return self.browsers_controller.browse_key_file()

    def browse_client_secrets_file(self):
        return self.browsers_controller.browse_client_secrets_file()

    def browse_local_directory(self):
        return self.browsers_controller.browse_local_directory()

    def browse_directory(self, line_edit: Optional[QLineEdit] = None):
        return self.browsers_controller.browse_directory(line_edit=line_edit)

    def browse_files(self):
        return self.browsers_controller.browse_files()

    def browse_input(self):
        return self.browsers_controller.browse_input()

    def browse_output(self):
        return self.browsers_controller.browse_output()

    # ------------------------------------------------------------------
    # Config facade
    # ------------------------------------------------------------------
    def collect(self) -> dict:
        return self.config_controller.collect()

    def get_default_config(self) -> dict:
        return self.config_controller.get_default_config()

    def set_config(self, config: dict):
        return self.config_controller.set_config(config)

    # ------------------------------------------------------------------
    # Defaults facade
    # ------------------------------------------------------------------
    def load_configuration_defaults(self):
        return self.defaults_controller.load_configuration_defaults()

    # ------------------------------------------------------------------
    # Provider facade
    # ------------------------------------------------------------------
    def get_provider_text(self) -> str:
        return self.provider_controller.get_provider_text()

    def handle_provider_change(self, index: int):
        return self.provider_controller.handle_provider_change(index)

    # ------------------------------------------------------------------
    # Remote map facade
    # ------------------------------------------------------------------
    def view_remote_map(self):
        return self.remote_map_controller.view_remote_map()

    @Slot(bool, str)
    def handle_view_finished(self, success: bool, message: str):
        return self.remote_map_controller.handle_view_finished(success, message)

    # ------------------------------------------------------------------
    # Share folder facade
    # ------------------------------------------------------------------
    def share_remote_folder(self):
        return self.share_folder_controller.share_remote_folder()

    @Slot(bool, str)
    def handle_share_finished(self, success: bool, message: str):
        return self.share_folder_controller.handle_share_finished(success, message)

    # ------------------------------------------------------------------
    # Sync worker facade
    # ------------------------------------------------------------------
    def toggle_sync(self):
        return self.sync_worker_controller.toggle_sync()

    def stop_sync_now(self):
        return self.sync_worker_controller.stop_sync_now()

    def run_sync_now(self, clear_log: bool = True, force_live: bool = False):
        return self.sync_worker_controller.run_sync_now(clear_log=clear_log, force_live=force_live)

    @Slot(str)
    def handle_status_update(self, msg: str):
        return self.sync_worker_controller.handle_status_update(msg)

    @Slot(bool, str, bool)
    def handle_sync_finished(self, success: bool, message: str, was_dry_run: bool):
        return self.sync_worker_controller.handle_sync_finished(success, message, was_dry_run)

    # ------------------------------------------------------------------
    # UI lock facade
    # ------------------------------------------------------------------
    def lock_ui(self, message: str, is_running: bool = False, clear_log: bool = False):
        return self.ui_lock_controller.lock_ui(message, is_running=is_running, clear_log=clear_log)

    def unlock_ui(self):
        return self.ui_lock_controller.unlock_ui()

    def lock_ui_minor(self, message: str, clear_log: bool = False):
        return self.ui_lock_controller.lock_ui_minor(message, clear_log=clear_log)

    def unlock_ui_minor(self):
        return self.ui_lock_controller.unlock_ui_minor()

    # ------------------------------------------------------------------
    # UI builder facade
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        return self.ui_builder._build_ui()

    # --- QML Integration Properties & Slots ---
    @Property(bool, notify=qml_settings_changed)
    def dry_run(self):
        return self.dry_run_checkbox.isChecked()

    @dry_run.setter
    def dry_run(self, val):
        self.dry_run_checkbox.setChecked(val)
        self.qml_settings_changed.emit()

    @Property(bool, notify=qml_settings_changed)
    def overwrite(self):
        return self._overwrite

    @overwrite.setter
    def overwrite(self, val):
        self._overwrite = val
        self.qml_settings_changed.emit()

    @Property(bool, notify=qml_settings_changed)
    def verify_integrity(self):
        return self._verify_integrity

    @verify_integrity.setter
    def verify_integrity(self, val):
        self._verify_integrity = val
        self.qml_settings_changed.emit()

    @Property(str, notify=qml_log_changed)
    def log_text(self):
        return self._log_text

    @Property(float, notify=qml_progress_changed)
    def progress_value(self):
        return self._progress_value

    @Slot()
    def start_sync_worker(self):
        self.run_sync_now(clear_log=True)

    @Slot()
    def stop_sync_worker(self):
        self.stop_sync_now()

    @Slot(str)
    def update_log_qml(self, msg):
        self._log_text += msg + "\n"
        self.qml_log_changed.emit()


__all__ = ["DriveSyncTab"]
