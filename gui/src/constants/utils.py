"""Constants relocated from backend/src or gui/src modules under this subpackage (module-level ALL_CAPS assignments)."""

from pathlib import Path

from PySide6.QtGui import QImageReader

# --- from gui/src/utils/image_load.py ---
_QT_NATIVE_EXTS = {fmt.data().decode().lower() for fmt in QImageReader.supportedImageFormats()}

# --- from gui/src/utils/guard/startup_probe_guard.py ---
_STARTUP_SETTLE_CEILING_SECONDS = 5.0

# --- from gui/src/utils/manager/shortcut_manager.py ---
_KEYBINDINGS_PATH = Path.home() / '.image-toolkit' / 'keybindings.json'
