import os

from pathlib import Path


# Paths
path = Path(os.getcwd())
parts = path.parts
ROOT_DIR = Path(*parts[:parts.index('Image-Toolkit') + 1])
ICON_FILE = os.path.join(ROOT_DIR, 'app', 'src', 'images', "image_toolkit_icon.png")

JAR_FILE = os.path.join(ROOT_DIR, 'cryptography', 'target', 'cryptography-1.0.0-SNAPSHOT-uber.jar')
KEYSTORE_FILE = os.path.join(ROOT_DIR, 'assets', "my_java_keystore.p12")
VAULT_FILE = os.path.join(ROOT_DIR, 'assets', "my_secure_data.vault")
KEY_ALIAS = os.path.join(ROOT_DIR, 'assets', "my-aes-key")

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