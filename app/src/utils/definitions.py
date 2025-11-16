import os

from pathlib import Path


# Paths
path = Path(os.getcwd())
parts = path.parts
ROOT_DIR = Path(*parts[:parts.index('Image-Toolkit') + 1])

JAR_FILE = os.path.join(ROOT_DIR, 'cryptography', 'target', 'cryptography-1.0.0-SNAPSHOT-uber.jar')
CRYPTO_DIR = os.path.join(ROOT_DIR, 'assets', 'cryptography')
KEYSTORE_FILE = os.path.join(CRYPTO_DIR, "my_java_keystore.p12")
VAULT_FILE = os.path.join(CRYPTO_DIR, "my_secure_data.vault")
PEPPER_FILE = os.path.join(CRYPTO_DIR, "pepper.txt")
KEY_ALIAS = os.path.join("my-aes-key")

IMAGES_DIR = os.path.join(ROOT_DIR, 'assets', 'images')
ICON_FILE = os.path.join(IMAGES_DIR, "image_toolkit_icon.png")

API_DIR = os.path.join(ROOT_DIR, 'assets', 'api')
SERVICE_ACCOUNT_FILE = os.path.join(API_DIR, "image_toolkit_service.json")
CLIENT_SECRETS_FILE = os.path.join(API_DIR, 'client_secret.json')
TOKEN_FILE = os.path.join(API_DIR, 'token.json')

LOCAL_SOURCE_PATH = os.path.join(ROOT_DIR, 'data')
DRIVE_DESTINATION_FOLDER_NAME = "data"

# GUI settings
CTRL_C_TIMEOUT = 2.0

APP_STYLES = ['fusion', 'windows', 'windowsxp', 'macintosh']

# Image manipulation
SUPPORTED_IMG_FORMATS = ['webp', 'avif', 'png', 'jpg', 'jpeg', 'bmp', 'gif', 'tiff']

# Web Crawler
WC_BROWSERS = ["brave", "firefox", "chrome", "edge", "safari"]

CRAWLER_TIME_OPEN = 120
CRAWLER_SETUP_WAIT_TIME = 15

# Database
START_TAGS = sorted([
    "landscape", "night", "day", "indoor", "outdoor",
    "solo", "multiple", "fanart", "official", "cosplay",
    "portrait", "full_body", "action", "close_up", "nsfw",
    "color", "monochrome", "sketch", "digital", "traditional"
])

# Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive']
SYNC_ERROR = "SyncFailed"

# Wallpaper style definitions (copied from wallpaper_tab for context)
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
        "Scaled": 0,
        "Scaled and Cropped (Zoom)": 6,
        "Centered": 3,
        "Tiled": 4,
        "Span (GNOME Fallback)": 2 
    },
    "GNOME": {
        "Span (Only Option)": "spanned"
    }
}