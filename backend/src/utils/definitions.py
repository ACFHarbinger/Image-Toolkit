import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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