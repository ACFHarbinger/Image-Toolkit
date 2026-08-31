import sys
from pathlib import Path

# Project Root
if getattr(sys, "frozen", False):
    ROOT_DIR = (
        Path(sys._MEIPASS)
        if hasattr(sys, "_MEIPASS")
        else Path(sys.executable).resolve().parent
    )
else:
    ROOT_DIR = Path(__file__).resolve().parents[3]

# System Dirs
IMAGE_TOOLKIT_DIR = Path.home() / ".image-toolkit"
THUMBNAIL_CACHE_DIR = IMAGE_TOOLKIT_DIR / "thumbnail-cache"
# Previously redeclared identically as _DEFAULT_INDEX_DIR in both
# core/cbir_search.py (reader) and models/tuning/cbir_index_builder.py (writer).
CBIR_INDEX_DIR = IMAGE_TOOLKIT_DIR / "cbir_index"

# Base Dirs
BACKEND_DIR = ROOT_DIR / "backend"
ASSETS_DIR = ROOT_DIR / "assets"
SECRETS_DIR = ASSETS_DIR / "secrets"
LOCAL_SECRETS_DIR = IMAGE_TOOLKIT_DIR / "secrets"
IMAGES_DIR = ASSETS_DIR / "images"
API_DIR = ASSETS_DIR / "api"
CONFIGS_DIR = ROOT_DIR / "configs"

# Files
_crypto_lib_name = "libitk_crypto.dll" if sys.platform == "win32" else "libitk_crypto.so"
if (ROOT_DIR / "build" / "crypto" / _crypto_lib_name).exists():
    CRYPTO_LIB_FILE = str(ROOT_DIR / "build" / "crypto" / _crypto_lib_name)
elif (ROOT_DIR / _crypto_lib_name).exists():
    CRYPTO_LIB_FILE = str(ROOT_DIR / _crypto_lib_name)
elif getattr(sys, "frozen", False) and (Path(sys.executable).resolve().parent / _crypto_lib_name).exists():
    CRYPTO_LIB_FILE = str(Path(sys.executable).resolve().parent / _crypto_lib_name)
else:
    CRYPTO_LIB_FILE = str(ROOT_DIR / "build" / "crypto" / _crypto_lib_name)

ICON_FILE = str(IMAGES_DIR / "image_toolkit_icon.png")
DAEMON_CONFIG_PATH = IMAGE_TOOLKIT_DIR / ".slideshow_config.json"
MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH = IMAGE_TOOLKIT_DIR / ".monitor_slideshow_daemon.json"

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
LOCAL_SOURCE_PATH = str(Path.home() / "Downloads" / "Data")
