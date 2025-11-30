import os

from pathlib import Path
from typing import Literal


# --- Base Paths (Static) ---
# Find the project root 'Image-Toolkit'
path = Path(os.getcwd())
parts = path.parts
try:
    ROOT_DIR = Path(*parts[:parts.index('Image-Toolkit') + 1])
except ValueError:
    print("Warning: 'Image-Toolkit' not in path. Using current working directory as root.")
    ROOT_DIR = path

JAR_FILE = os.path.join(ROOT_DIR, 'cryptography', 'build', 'libs', 'cryptography-1.0.0-SNAPSHOT.jar')
CRYPTO_DIR = os.path.join(ROOT_DIR, 'assets', 'cryptography')
IMAGES_DIR = os.path.join(ROOT_DIR, 'assets', 'images')
API_DIR = os.path.join(ROOT_DIR, 'assets', 'api')
LOCAL_SOURCE_PATH = os.path.join(os.path.dirname(os.path.dirname(ROOT_DIR)), 'Downloads', 'data')

# --- Base File Definitions ---
# These are the "templates" or defaults
BASE_KEYSTORE_FILE = os.path.join(CRYPTO_DIR, "my_keystore.p12")
BASE_VAULT_FILE = os.path.join(CRYPTO_DIR, "my_secure_data.vault")
BASE_PEPPER_FILE = os.path.join(CRYPTO_DIR, "pepper.txt")

# --- Static Files (Not account-specific) ---
# These files are shared across all accounts
ICON_FILE = os.path.join(IMAGES_DIR, "image_toolkit_icon.png")
GOOGLE_API_FILE = os.path.join(API_DIR, 'google_api_key.json')
SERVICE_ACCOUNT_FILE = os.path.join(API_DIR, "image_toolkit_service.json")
CLIENT_SECRETS_FILE = os.path.join(API_DIR, 'client_secret.json')

# --- Active Dynamic Paths (Mutable) ---
# These are the variables that other modules will import and use.
# They default to the base paths and are changed by update_cryptographic_values.
KEYSTORE_FILE = BASE_KEYSTORE_FILE
VAULT_FILE = BASE_VAULT_FILE
PEPPER_FILE = BASE_PEPPER_FILE

# Dynamic file not to be shared
TOKEN_FILE = os.path.join(API_DIR, 'token.json')

# --- Constants ---
KEY_ALIAS = "my-aes-key" # This is an alias *inside* the keystore
CTRL_C_TIMEOUT = 2.0
APP_STYLES = ['fusion', 'windows', 'windowsxp', 'macintosh']
SUPPORTED_IMG_FORMATS = ['webp', 'avif', 'png', 'jpg', 'jpeg', 'bmp', 'gif', 'tiff']
SUPPORTED_VIDEO_FORMATS = {'.mp4', '.mkv', '.webm', '.mov', ".avi", '.gif'}

# Crawler constants
WC_BROWSERS = ["brave", "firefox", "chrome", "edge", "safari"]
CRAWLER_TIME_OPEN = 120
CRAWLER_SETUP_WAIT_TIME = 15

# Drive synchronization constants 
DRIVE_DESTINATION_FOLDER_NAME = "data"
SCOPES = ['https://www.googleapis.com/auth/drive']
SYNC_ERROR = "SyncFailed"
GRAPH_API_ENDPOINT = 'https://graph.microsoft.com/v1.0'

# Other constants
DAEMON_CONFIG_PATH = Path.home() / ".myapp_slideshow_config.json"

WALLPAPER_STYLES = {
    "Windows": {
        "Fill": ("4", "0"), "Fit": ("6", "0"), "Stretch": ("2", "0"),
        "Center": ("0", "0"), "Tile": ("0", "1"),
    },
    "KDE": {
        "Scaled, Keep Proportions": 1, "Scaled": 2, "Scaled and Cropped (Zoom)": 0,
        "Centered": 6, "Tiled": 3, "Center Tiled": 4, "Span": 5
    },
    "GNOME": {
        "None": "none", "Wallpaper": "wallpaper", "Centered": "centered",
        "Scalled": "scalled", "Stretched": "stretched", "Zoom": "zoom", "Spanned": "spanned",
    }
}

# Define the set of allowed alignment modes for clarity
AlignMode = Literal[
    "Default (Top/Center)", 
    "Align Top/Left", 
    "Align Bottom/Right", 
    "Center", 
    "Scaled (Grow Smallest)", 
    "Squish (Shrink Largest)"
]

# Functions
def _get_suffixed_path(base_path, suffix):
    """
    Helper function to create a new path with an account suffix.
    Example: (path/to/file.json, "userA") -> path/to/file-userA.json
    """
    if not suffix:
        return base_path # Return base path if suffix is empty
    
    # Basic sanitization to prevent path traversal or invalid characters
    safe_suffix = "".join(c for c in suffix if c.isalnum() or c in ('-', '_', '.')).rstrip()
    if not safe_suffix:
        return base_path # Suffix was invalid (e.g., "!!")
        
    directory, filename = os.path.split(base_path)
    name, ext = os.path.splitext(filename)
    new_filename = f"{name}-{safe_suffix}{ext}"
    return os.path.join(directory, new_filename)


def update_cryptographic_values(account_name):
    """
    Updates the global path variables for account-specific files.
    This MUST be called by the login window *before* initializing
    the JavaVaultManager.
    """
    # Use 'global' to modify the top-level variables in this module
    global KEYSTORE_FILE, VAULT_FILE, PEPPER_FILE

    print(f"Updating cryptographic paths for account: {account_name}")
    
    # These files are unique to the user:
    # Keystore (holds key), Vault (holds data), Pepper (for hashing)
    KEYSTORE_FILE = _get_suffixed_path(BASE_KEYSTORE_FILE, account_name)
    VAULT_FILE = _get_suffixed_path(BASE_VAULT_FILE, account_name)
    PEPPER_FILE = _get_suffixed_path(BASE_PEPPER_FILE, account_name)

    print("--- DEFINITIONS UPDATED ---")
    print(f"KEYSTORE_FILE set to: {KEYSTORE_FILE}")
    print(f"VAULT_FILE set to: {VAULT_FILE}")
    print(f"PEPPER_FILE set to: {PEPPER_FILE}")
    print("---------------------------")
