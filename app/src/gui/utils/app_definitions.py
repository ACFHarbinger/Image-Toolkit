# --- GLOBAL CONFIGURATION (MOCK DATA for QLineEdit defaults) ---
DRY_RUN = False

# New image size limit
NEW_LIMIT_MB = 1024

# Define common wallpaper styles and their OS-specific representations for Windows and KDE
WALLPAPER_STYLES = {
    # Windows: (Registry Value, Tile Value)
    "Windows": {
        "Fill": ("4", "0"),
        "Fit": ("6", "0"),
        "Stretch": ("2", "0"),
        "Center": ("0", "0"),
        "Tile": ("0", "1"),
    },
    # KDE/Plasma: (FillMode Integer)
    "KDE": {
        "Scaled, Keep Proportions": 1,
        "Scaled": 0,
        "Scaled and Cropped (Zoom)": 6,
        "Centered": 3,
        "Tiled": 4,
        "Span (GNOME Fallback)": 2 # Used internally for GNOME
    },
    # GNOME Fallback uses 'spanned' option for the composed image
    "GNOME": {
        "Span (Only Option)": "spanned"
    }
}