"""Constants relocated from backend/src or gui/src modules under this subpackage (module-level ALL_CAPS assignments)."""

# --- from gui/src/windows/settings/_shortcuts.py ---
_SCOPE_ICONS = {'General': '🖥️', 'Gallery': '🖼️', 'Preview': '🔍'}
_DEFAULT_SCOPE_ICON = '🔧'

# --- from gui/src/windows/settings/app_config.py ---
_KNOWN_GUI_KEYS = frozenset({'mainwindow/geometry', 'preferences/recursive_scan', 'preferences/favourite_directories', 'preferences/mal_fetch_method'})

# --- from gui/src/windows/main/_global_search.py ---
_NESTED_GALLERY_ATTRS = ('format_subtab', 'codec_subtab', 'sampler_subtab')
_MAX_RESULTS = 200
