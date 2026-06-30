---
description: Template and rules for creating a thread-safe QRunnable/QThread worker in gui/src/helpers/.
---

You are a Qt/Python concurrency expert working on the Image-Toolkit PySide6 app.

## Task: Add a Background Worker

This codebase uses two worker patterns. Choose the right one:

| Pattern | When to use |
|---|---|
| `QRunnable` + `QThreadPool` | Short/batched tasks (image loading, file scans). Low overhead. |
| `QThread` + `QObject` | Long-running or cancellable tasks (crawlers, conversions). Supports `requestInterruption()`. |

---

## Pattern A — QRunnable (preferred for short tasks)

Create `gui/src/helpers/core/<name>_worker.py`:

```python
from PySide6.QtCore import QRunnable, QObject, Signal, Slot
from PySide6.QtGui import QImage

class MyWorkerSignals(QObject):
    result = Signal(list)      # adjust type to match your output
    error  = Signal(str)
    progress = Signal(int)     # optional: 0–100

class MyWorker(QRunnable):
    def __init__(self, paths: list[str]):
        super().__init__()
        self.paths = paths
        self.signals = MyWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            # Call Rust or backend logic here — never touch Qt widgets
            import base
            result = base.some_function(self.paths)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
```

Dispatch from the tab:

```python
worker = MyWorker(paths)
worker.signals.result.connect(self._on_result)
worker.signals.error.connect(self._on_error)
QThreadPool.globalInstance().start(worker)
```

---

## Pattern B — QThread (for long-running/cancellable tasks)

```python
from PySide6.QtCore import QThread, Signal

class MyLongWorker(QThread):
    progress = Signal(int)
    finished = Signal(list)
    error    = Signal(str)

    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self.items = items

    def run(self):
        results = []
        for i, item in enumerate(self.items):
            if self.isInterruptionRequested():
                break
            # process item…
            results.append(item)
            self.progress.emit(int((i + 1) / len(self.items) * 100))
        self.finished.emit(results)
```

Start/stop from tab:

```python
self._worker = MyLongWorker(items, parent=self)
self._worker.finished.connect(self._on_done)
self._worker.start()

# To cancel:
self._worker.requestInterruption()
self._worker.wait()
```

---

## Critical Thread-Safety Rules

1. **Never create `QPixmap` in a worker** — `QPixmap` is main-thread only. Emit `QImage` and convert with `QPixmap.fromImage()` in the slot.
2. **Never call widget methods from `run()`** — only emit signals; slots on the main thread update the UI.
3. **Never use `QFileDialog` with GTK native dialogs** — always pass `QFileDialog.Option.DontUseNativeDialog` (JVM crash risk).
4. Keep `_active_workers` set in the tab to prevent Python from GC-ing workers before signals fire.

## Export

Add to `gui/src/helpers/core/__init__.py`:

```python
from .my_worker import MyWorker
```

## Checklist
- [ ] Signals defined in a separate `QObject` subclass (for `QRunnable`)
- [ ] `setAutoDelete(True)` set on `QRunnable`
- [ ] Worker emits `QImage`, not `QPixmap`
- [ ] No widget updates inside `run()`
- [ ] Worker class added to `gui/src/helpers/core/__init__.py`
- [ ] App runs without freezes after the worker dispatches
