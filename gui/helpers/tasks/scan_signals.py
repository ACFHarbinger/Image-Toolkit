from PySide6.QtCore import QObject, Signal


class ScanSignals(QObject):
    """
    Signals for individual worker tasks.
    Must be a QObject to emit signals, but QRunnable is not a QObject.
    """
    result = Signal(object)  # Emits tuple (path, data)
    error = Signal(str)
