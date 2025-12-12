import os

from pathlib import Path

# --- Base Paths (Static) ---
# Find the project root 'Image-Toolkit'
path = Path(os.getcwd())
parts = path.parts
try:
    ROOT_DIR = Path(*parts[: parts.index("Image-Toolkit") + 1])
except ValueError:
    print(
        "Warning: 'Image-Toolkit' not in path. Using current working directory as root."
    )
    ROOT_DIR = path

SCREENSHOTS_DIR = os.path.join(ROOT_DIR, "screenshots")

# --- GLOBAL CONFIGURATION (MOCK DATA for QLineEdit defaults) ---
DRY_RUN = False

# New image size limit
NEW_LIMIT_MB = 10000
