from pathlib import Path

# Project Root
ROOT_DIR = Path(__file__).resolve().parents[3]

# System Dirs
IMAGE_TOOLKIT_DIR = Path.home() / ".image-toolkit"
THUMBNAIL_CACHE_DIR = IMAGE_TOOLKIT_DIR / "thumbnail-cache"

# Base Dirs
BACKEND_DIR = ROOT_DIR / "backend"
ASSETS_DIR = ROOT_DIR / "assets"
SECRETS_DIR = ASSETS_DIR / "secrets"
LOCAL_SECRETS_DIR = IMAGE_TOOLKIT_DIR / "secrets"
IMAGES_DIR = ASSETS_DIR / "images"
API_DIR = ASSETS_DIR / "api"

# Files
JAR_FILE = str(
    ROOT_DIR / "cryptography" / "build" / "libs" / "cryptography-1.0.0-SNAPSHOT.jar"
)
ICON_FILE = str(IMAGES_DIR / "image_toolkit_icon.png")
DAEMON_CONFIG_PATH = IMAGE_TOOLKIT_DIR / ".slideshow_config.json"

# API / Auth Files
GOOGLE_API_FILE = str(API_DIR / "google_api_key.json")
SERVICE_ACCOUNT_FILE = str(API_DIR / "image_toolkit_service.json")
CLIENT_SECRETS_FILE = str(API_DIR / "client_secret.json")
TOKEN_FILE = str(API_DIR / "token.json")

# Secrets Files (Templates/Defaults)
BASE_KEYSTORE_FILE = str(SECRETS_DIR / "my_keystore.p12")
BASE_VAULT_FILE = str(SECRETS_DIR / "my_secure_data.vault")
BASE_PEPPER_FILE = str(SECRETS_DIR / "pepper.txt")

# Other
LOCAL_SOURCE_PATH = str(ROOT_DIR.parent.parent / "Downloads" / "data")
