---
description: Diagnostic checklist for JVM/Qt/Rust native crashes (SIGSEGV, SIGABRT) in Image-Toolkit.
---

You are a systems-level debugger. Image-Toolkit runs JPype (JVM), PySide6 (Qt), and PyO3 (Rust) in the same process. Native crashes are almost always caused by one of three root causes.

## Crash Triage: Read the Log First

Check `hs_err_pid*.log` in the repo root — the JVM writes these on fatal crash. Also check the terminal output for Qt/Python tracebacks.

---

## Root Cause A — JVM ↔ Native Dialog Crash (most common)

**Symptom**: `SIGSEGV` in `__dynamic_cast` (`libstdc++.so.6`) after a file dialog opens.

**Cause**: `QFileDialog` using the GTK portal loads GTK's `libstdc++`, which conflicts with JPype's JVM `libstdc++` symbols (RTTI clash in the same process).

**Fix**: Every `QFileDialog` call must pass `DontUseNativeDialog`:

```python
QFileDialog.getExistingDirectory(
    self, "Select", "",
    QFileDialog.Option.DontUseNativeDialog
)
QFileDialog.getOpenFileName(
    self, "Open", "",
    "Images (*.png *.jpg)",
    options=QFileDialog.Option.DontUseNativeDialog
)
```

**Search for violations**:
```bash
grep -rn "QFileDialog" gui/ --include="*.py" | grep -v DontUseNativeDialog
```

---

## Root Cause B — QWebEngineView / Chromium Crash

**Symptom**: Crash in `libpyside6.abi3.so.6.*` when a tab containing `QWebEngineView` is first shown. Log contains "Fallback to Vulkan rendering in Chromium".

**Cause**: Chromium loads Vulkan/GBM native libs on first paint, triggering the same RTTI conflict as Root Cause A.

**Fix**: Never use `QWebEngineView`. Open URLs with:

```python
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
QDesktopServices.openUrl(QUrl("https://example.com"))
```

**Search for violations**:
```bash
grep -rn "QWebEngineView\|QtWebEngine" gui/ --include="*.py"
```

---

## Root Cause C — QPixmap Created in Worker Thread

**Symptom**: Assertion failure or crash in `QPixmap` constructor. Stack trace points to a `QRunnable` or `QThread`.

**Cause**: `QPixmap` is main-thread only (X11 backing store). Creating it in a thread pool worker is undefined behaviour.

**Fix**: Emit `QImage` from workers; convert on the main thread:

```python
# In worker — safe:
self.signals.result.emit(q_image)  # QImage is thread-safe

# In slot on main thread:
pixmap = QPixmap.fromImage(q_image)
label.setPixmap(pixmap)
```

**Search for violations**:
```bash
grep -rn "QPixmap()" gui/src/helpers/ --include="*.py"
```

---

## Other Checks

| Symptom | Likely cause | Fix |
|---|---|---|
| Crash only on second window open | Widget deleted while signal connected | Hold a reference; check `sip.isValid()` |
| Freeze (not crash) | Blocking call on main thread | Move to `QRunnable`/`QThread` worker |
| `ImportError: base` | Rust module not built | `cd base && maturin develop --features python` |
| Celery task hangs | DB connection leak | Ensure `conn.close()` in all paths |

## Quick Diagnostic Commands

```bash
# Check for native dialog usage without DontUseNativeDialog
grep -rn "QFileDialog" gui/ --include="*.py" | grep -v DontUseNativeDialog

# Check for QWebEngineView usage
grep -rn "QWebEngineView" gui/ --include="*.py"

# Check for QPixmap in workers
grep -rn "QPixmap" gui/src/helpers/ --include="*.py"

# View the latest JVM crash log
ls -t hs_err_pid*.log | head -1 | xargs tail -50
```
