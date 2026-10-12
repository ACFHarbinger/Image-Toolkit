"""Keep cancelled QThreads alive independently of their disposed UI owner."""

from collections.abc import Callable

from PySide6.QtCore import QTimer

_retained: dict[int, tuple[object, QTimer]] = {}


def retain_until_stopped(worker, callback: Callable[[], None] | None = None) -> None:
    # BaseQThreadWorker.finished carries a result before run() has returned.
    # wait(0), unlike that signal, verifies actual thread completion.
    key = id(worker)
    if key in _retained:
        return
    timer = QTimer()
    timer.setInterval(25)

    def reap() -> None:
        if not worker.wait(0):
            return
        timer.stop()
        _retained.pop(key, None)
        try:
            if callback is not None:
                callback()
        finally:
            timer.deleteLater()

    timer.timeout.connect(reap)
    _retained[key] = (worker, timer)
    timer.start()
