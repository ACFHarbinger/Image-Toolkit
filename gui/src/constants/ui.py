from PySide6.QtGui import QColor

# UI Behavior
ZOOM_STEP = 1.1
LAG_COMPENSATION_MS = 300
MAX_PREVIEW_ITEMS = 100

# Window Titles
DEFAULT_WINDOW_TITLE = "Image Toolkit"

# Component Sizes
DEFAULT_THUMBNAIL_SIZE = (128, 128)

# Hybrid Stitch Panel
STITCH_THUMB_W = 96
STITCH_THUMB_H = 54
STITCH_CP_COLORS = [
    "#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#9b59b6", "#1abc9c",
    "#e67e22", "#ecf0f1", "#95a5a6", "#d35400", "#c0392b", "#2980b9",
]
DARK_PANEL_STYLE = "background:#2c2f33;"
DARK_GROUP_STYLE = "QGroupBox { background:#2c2f33; color:#ccc; }"
DARK_TABLE_STYLE = "QTableWidget { background:#23272a; border:1px solid #4f545c; gridline-color:#2c2f33; selection-background-color:#7289da; }"

# Stitch Tab Node Graph
CONF_HIGH = QColor(80, 220, 80, 180)
CONF_MED = QColor(220, 200, 40, 160)
CONF_LOW = QColor(220, 60, 60, 140)
ANCHOR_RADIUS = 5
MAX_DISPLAYED_MATCHES = 150
PORT_RADIUS = 6
NODE_WIDTH = 220
NODE_HDR_HEIGHT = 26
NODE_BODY_HEIGHT = 52
NODE_THUMB_HEIGHT = 110
EDGE_COLOR = QColor(80, 200, 255, 200)

SIZE_PRESETS = [
    ("Default (Full)", "full"),
    ("720p (HD)", (1280, 720)),
    ("1080p (FHD)", (1920, 1080)),
    ("1440p (QHD)", (2560, 1440)),
    ("4K (UHD)", (3840, 2160)),
    ("Portrait (TikTok)", (1080, 1920)),
    ("Twitter/X", (1200, 675)),
]

CROP_PRESETS = [
    ("None", None),
    ("16:9", 16 / 9),
    ("4:3", 4 / 3),
    ("2.39:1 (Cinema)", 2.39),
    ("1:1 (Square)", 1.0),
    ("9:16 (Portrait)", 9 / 16),
]

ANIM_CLUSTER_COLORS = [
    "#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#9b59b6", "#1abc9c",
    "#e67e22", "#ecf0f1", "#95a5a6", "#27ae60", "#2980b9", "#8e44ad",
]
