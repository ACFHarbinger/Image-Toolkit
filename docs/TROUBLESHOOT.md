# Troubleshooting SIGSEGV Crashes in Image-Toolkit

## 🚨 Symptom: Sudden Crash with `__dynamic_cast` failure

The application terminates abruptly, typically during video conversion, batch gallery loading, or at startup during vault decryption.
The crash log (`hs_err_pid*.log`) shows a failure at:
`C [libstdc++.so.6+0xc1e25] __dynamic_cast+0x35`

## 🔍 Root Cause Analysis

### 1. Unsafe Signal Lifecycle in `QRunnable` (Shiboken)

**Context**: The `LoaderWorker` and `BatchLoaderWorker` (Image/Video) classes use `setAutoDelete(True)` and own a member `signals` (`QObject`).
**Failure**: When the worker's `run()` method returns, it is immediately deleted. If a `Signal.emit()` has been called, but the signal hasn't finished delivery by the main thread's event loop, the `signals` object is destroyed before the delivery is complete.
**Fix**: Added `self.signals.deleteLater()` in a `finally` block at the end of the `run()` method. This schedules the signals object for safe deletion _after_ any pending signals are handled.

### 2. Incomplete Worker Cleanup during Tab Closure

**Context**: Closing `ConvertTab` or `GalleryTab` while background threads are active.
**Failure**: Active workers continue to run and emit signals. If the receiving tab/widget is deleted, Shiboken crashes during the type translation of the signal arguments.
**Fix**: Overrode `closeEvent` for all tabs using long-running workers. Specifically updated `ConvertTab` to call `cancel_conversion()` (which calls `worker.wait()`) and `AbstractClassTwoGalleries` to clear and potentially wait for thread pool tasks.

### 3. JNI/JPype Threading Race Conditions

**Context**: Concurrent access to the Java-based `VaultManager` during startup or background scanning.
**Failure**: Memory corruption in the JNI bridge between `JPype` (Java) and `Shiboken` (Qt/Python) during `__dynamic_cast`.
**Fix**: Added a `threading.RLock` to `VaultManager` to synchronize all JNI operations.

### 4. Widget Parent/Ownership Conflicts

**Context**: Reusing persistent widgets (like `MonitorDropWidget`) across transient layout containers.
**Failure**: Calling `deleteLater()` on a container which implicitly deletes its children, even if those children were intended for reuse.
**Fix**: Explicitly `setParent(None)` on the child widget before deleting the parent layout/container.

## 🛠️ Developer Best Practices (Prevention)

1. **Signal Safety**: Use `deleteLater()` on all `QObject` members of `QRunnable` if using `setAutoDelete(True)`.
2. **Graceful Exit**: Always handle `closeEvent` and ensure any active `QThread` or `QProcess` is halted before the widget object is destroyed.
3. **Bridge Sync**: Synchronize access to any bridge/transpiler (JPype/Rust) if accessed across different threads to prevent JNI memory corruption.
4. **Native Dialogs**: On Linux, avoid `DontUseNativeDialog` in `QFileDialog`. Using the native OS dialog avoids internal C++ RTTI conflicts between custom Qt widgets and the Wayland backend.
