---
description: Step-by-step guide to adding a new feature tab to the PySide6 desktop GUI.
---

You are a Qt/Python expert working on the Image-Toolkit PySide6 desktop application.

## Task: Add a New GUI Tab

Follow these steps in order. Do not skip steps.

### 1. Create the Tab Widget

Create `gui/src/tabs/core/<name>_tab.py`. Choose the right base class:

- `AbstractClassTwoGalleries` — tabs that show two image galleries (found / selected), e.g. convert, merge, delete.
- `AbstractClassSingleGallery` — tabs with one gallery and monitor/display logic, e.g. wallpaper.
- Plain `QWidget` — for non-gallery utility tabs.

```python
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton

class MyFeatureTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # add widgets…
```

### 2. Move Heavy Work Off the Main Thread

Any I/O, Rust call, or CPU work → put in `gui/src/helpers/core/<name>_worker.py`.

```python
from PySide6.QtCore import QRunnable, QObject, Signal

class MyWorkerSignals(QObject):
    finished = Signal(list)   # result type
    error = Signal(str)

class MyWorker(QRunnable):
    def __init__(self, ...):
        super().__init__()
        self.signals = MyWorkerSignals()
        self.setAutoDelete(True)

    def run(self):
        try:
            result = ...  # call base.* or backend functions here
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
```

**NEVER** create `QPixmap` in a worker thread — emit `QImage` instead.

### 3. File Dialog Safety (JVM Crash Prevention)

Every `QFileDialog` call **must** include `DontUseNativeDialog`:

```python
path = QFileDialog.getExistingDirectory(
    self, "Select Folder", "",
    QFileDialog.Option.DontUseNativeDialog
)
```

Omitting this flag crashes the app via JVM/libstdc++ RTTI conflict on Linux.

### 4. Register the Tab in MainWindow

In `gui/src/windows/main_window.py`:

```python
from ..tabs.core.my_feature_tab import MyFeatureTab

# inside __init__ or _setup_tabs():
self.my_feature_tab = MyFeatureTab()
self.tab_widget.addTab(self.my_feature_tab, "My Feature")
```

### 5. Export from the tabs package

Add to `gui/src/tabs/core/__init__.py`:

```python
from .my_feature_tab import MyFeatureTab
```

### 6. Styling

- Use constants from `gui/src/styles/style.py` (do not hardcode colors/fonts).
- Use `apply_shadow_effect()` for card-like widgets.
- Apply QSS via `setStyleSheet()` rather than palette calls.

## Checklist Before Finishing
- [ ] No blocking I/O on the main thread
- [ ] All `QFileDialog` calls use `DontUseNativeDialog`
- [ ] Workers emit `QImage`, not `QPixmap`
- [ ] Tab registered in `main_window.py`
- [ ] No `gui/` imports inside `backend/` or `base/`
- [ ] App launches without error: `source .venv/bin/activate && python main.py`
