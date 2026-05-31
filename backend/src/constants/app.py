from typing import Literal

CTRL_C_TIMEOUT = 2.0
APP_STYLES = ["fusion", "windows", "windowsxp", "macintosh"]
SUPPORTED_IMG_FORMATS = ["webp", "avif", "png", "jpg", "jpeg", "bmp", "gif", "tiff"]
SUPPORTED_VIDEO_FORMATS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".wmv"}

AlignMode = Literal[
    "Default (Top/Center)",
    "Align Top/Left",
    "Align Bottom/Right",
    "Center",
    "Scaled (Grow Smallest)",
    "Squish (Shrink Largest)",
]

WALLPAPER_STYLES = {
    "Windows": {
        "Fill": ("4", "0"),
        "Fit": ("6", "0"),
        "Stretch": ("2", "0"),
        "Center": ("0", "0"),
        "Tile": ("0", "1"),
    },
    "KDE": {
        "Scaled, Keep Proportions": 1,
        "Scaled": 1,
        "Scaled and Cropped (Zoom)": 2,
        "Scaled and Cropped": 2,
        "Centered": 3,
        "Stretch": 0,
        "Tiled": 4,
        "Center Tiled": 5,
        "Span": 6,
    },
    "GNOME": {
        "None": "none",
        "Wallpaper": "wallpaper",
        "Centered": "centered",
        "Scalled": "scalled",
        "Stretched": "stretched",
        "Zoom": "zoom",
        "Spanned": "spanned",
    },
}
