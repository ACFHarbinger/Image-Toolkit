"""Constants relocated from backend/src or gui/src modules under this subpackage (module-level ALL_CAPS assignments)."""

# --- from gui/src/windows/settings/_shortcuts.py ---
_SCOPE_ICONS = {'General': '🖥️', 'Gallery': '🖼️', 'Preview': '🔍'}
_DEFAULT_SCOPE_ICON = '🔧'

# --- from gui/src/windows/settings/app_config.py ---
_KNOWN_GUI_KEYS = frozenset({'mainwindow/geometry', 'preferences/recursive_scan', 'preferences/favourite_directories', 'preferences/mal_fetch_method'})

# --- from gui/src/windows/main/_global_search.py ---
# WallpaperTab's system_display/monitor_display subtabs added for #545
# (architecture deep-dive finding: WallpaperTab's files were silently
# excluded from Ctrl+Shift+F global search -- neither WallpaperTab itself
# nor either subtab was ever checked, since master_image_paths lives on
# wallpaper_common_base, one level below the top-level tab object).
_NESTED_GALLERY_ATTRS = (
    'format_subtab',
    'codec_subtab',
    'sampler_subtab',
    'system_display',
    'monitor_display',
)
_MAX_RESULTS = 200
