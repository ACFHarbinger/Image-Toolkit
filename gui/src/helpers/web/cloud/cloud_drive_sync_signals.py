from PySide6.QtCore import QObject, Signal


class CloudDriveSyncWorkerSignals(QObject):
    status_update = Signal(str)
    # success, message, is_dry_run
    sync_finished = Signal(bool, str, bool)
