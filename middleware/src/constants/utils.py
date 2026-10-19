"""Constants relocated from middleware/src or gui/src modules under this subpackage (module-level ALL_CAPS assignments)."""

from pathlib import Path

# --- from middleware/src/utils/display/monitor_slideshow_daemon.py ---
DEFAULT_ENTRY_DURATION_SEC = 30.0
LOG_PATH = Path.home() / '.image-toolkit' / 'logs' / 'monitor_slideshow_daemon.log'

# --- from middleware/src/utils/display/slideshow_daemon.py ---
_VIDEO_DURATION_CACHE: dict[str, float] = {}
DISPLAY_LOG_PATH = Path.home() / '.image-toolkit' / 'logs' / 'slideshow_daemon.log'
PID_PATH = Path.home() / '.image-toolkit' / '.slideshow_daemon.pid'
