from backend.src.constants import IMAGE_TOOLKIT_DIR

# Constants and Storage Files
LISTINGS_FILE = IMAGE_TOOLKIT_DIR / "listings.json"
ENTITIES_FILE = IMAGE_TOOLKIT_DIR / "entities.json"
LISTING_IMAGES_DIR = IMAGE_TOOLKIT_DIR / "listing-images"

# Content Listing Configs
ENTRY_TYPES = ["Anime", "Movie", "Show", "Book", "Manga", "Game", "Other"]
ENTRY_STATUS = [
    "Completed",
    "Watching / Reading",
    "On Hold",
    "Dropped",
    "Plan to Watch",
]

TYPE_COLORS = {
    "Anime": "#e91e63",
    "Movie": "#2196f3",
    "Show": "#4caf50",
    "Book": "#ff9800",
    "Manga": "#9c27b0",
    "Game": "#00bcd4",
    "Other": "#607d8b",
}
STATUS_COLORS = {
    "Completed": "#2ecc71",
    "Watching / Reading": "#3498db",
    "On Hold": "#f39c12",
    "Dropped": "#e74c3c",
    "Plan to Watch": "#95a5a6",
}

# Entity Listing Configs
ENTITY_TYPES = ["Person", "Organization", "Fictional Character", "Other"]
ENTITY_ROLES = [
    "Actor / Seiyuu",
    "Director",
    "Producer",
    "Writer",
    "Studio",
    "Publisher",
    "Fictional Character",
    "Other",
]

ENTITY_TYPE_COLORS = {
    "Person": "#e91e63",
    "Organization": "#2196f3",
    "Fictional Character": "#ff9800",
    "Other": "#607d8b",
}
ENTITY_ROLE_COLORS = {
    "Director": "#4caf50",
    "Producer": "#9c27b0",
    "Writer": "#8e44ad",
    "Actor / Seiyuu": "#00bcd4",
    "Studio": "#e91e63",
    "Publisher": "#2196f3",
    "Fictional Character": "#ff9800",
    "Other": "#607d8b",
}

CARD_SIZE = 180
THUMB_SIZE = 130
PLACEHOLDER = "📽"  # shown when no image is set
ENTITY_PLACEHOLDER = "👤"

# Extensions recognised as importable video files
VIDEO_IMPORT_EXTS = {
    ".mkv", ".mp4", ".avi", ".mov", ".webm", ".flv", ".m4v",
    ".wmv", ".ts", ".m2ts", ".mpg", ".mpeg",
}
