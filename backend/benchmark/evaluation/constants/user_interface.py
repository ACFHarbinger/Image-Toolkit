"""
Image-Toolkit Backend Evaluation User Interface Constants

Contains constants used in the backend evaluation UI submodule.
"""

# Matplotlib figures configs
FIG_BG = "#12121f"
AX_BG = "#1a1a2e"

# Canvas mode options and elements
MODE_NAVIGATE = "navigate"
MODE_BBOX = "bbox"
MODE_POINT = "point"

# Canvas display options
DISPLAY_RAW = "display"
DISPLAY_PIXEL = "pixel"

# Dashboard zoom range and threshold
ZOOM_MIN = 0.05
ZOOM_MAX = 40.0
PIXEL_GRID_ZOOM_THRESHOLD = 8.0  # above this zoom, Pixel Value Mode overlays numeric text

# Scoring
SCORE_SCALE_HINT = "4=keepable  3=minor flaw  2=flawed but parses  1=mostly broken  0=incoherent"