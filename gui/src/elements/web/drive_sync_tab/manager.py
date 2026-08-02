"""``DriveSyncTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtWidgets import QWidget

from ....windows.logging import LogWindow
from ._auth_config import _AuthConfigMixin
from ._browsers import _BrowsersMixin
from ._config import _ConfigMixin
from ._defaults import _DefaultsMixin
from ._provider_switch import _ProviderSwitchMixin
from ._remote_map import _RemoteMapMixin
from ._share_folder import _ShareFolderMixin
from ._sync_worker import _SyncWorkerMixin
from ._ui_builder import _UIBuilderMixin
from ._ui_lock import _UILockMixin


class DriveSyncTab(
    _UIBuilderMixin,
    _ProviderSwitchMixin,
    _AuthConfigMixin,
    _DefaultsMixin,
    _RemoteMapMixin,
    _ShareFolderMixin,
    _SyncWorkerMixin,
    _UILockMixin,
    _BrowsersMixin,
    _ConfigMixin,
    QWidget,
):
    """GUI tab for Cloud Drive one-way sync (QRunnable + QThreadPool)."""

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

        self._build_ui()

    # --- QML Integration ---
    qml_settings_changed = Signal()
    qml_log_changed = Signal()
    qml_progress_changed = Signal()

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
        # Wrapper for QML
        # QML doesn't pass args, relies on properties.
        # Run sync uses widget state.
        self.run_sync_now(clear_log=True)

    @Slot()
    def stop_sync_worker(self):
        self.stop_sync_now()

    @Slot(str)
    def update_log_qml(self, msg):
        self._log_text += msg + "\n"
        self.qml_log_changed.emit()


__all__ = ["DriveSyncTab"]
