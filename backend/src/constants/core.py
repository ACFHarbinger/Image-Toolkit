"""Constants relocated from backend/src or gui/src modules under this subpackage (module-level ALL_CAPS assignments)."""

import importlib.util as _importlib_util_merger
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from backend.src.core.similarity.embedder import BaseEmbedder

# --- from backend/src/core/video_converter.py ---
VIDEO_CODEC_ENCODERS = {'h264': ('libx264', ['-pix_fmt', 'yuv420p']), 'hevc': ('libx265', ['-pix_fmt', 'yuv420p', '-tag:v', 'hvc1']), 'av1': ('libsvtav1', ['-pix_fmt', 'yuv420p']), 'vp9': ('libvpx-vp9', ['-pix_fmt', 'yuv420p', '-b:v', '0'])}
AUDIO_CODEC_ENCODERS = {'aac': ('aac', ['-b:a', '192k']), 'opus': ('libopus', ['-b:a', '128k']), 'mp3': ('libmp3lame', ['-q:a', '2']), 'flac': ('flac', [])}
_SPEED_PRESETS = {'h264': {0: 'ultrafast', 1: 'faster', 2: 'medium', 3: 'slow', 4: 'veryslow'}, 'hevc': {0: 'ultrafast', 1: 'faster', 2: 'medium', 3: 'slow', 4: 'veryslow'}, 'av1': {0: '12', 1: '10', 2: '8', 3: '5', 4: '2'}, 'vp9': {0: '8', 1: '6', 2: '4', 3: '2', 4: '0'}}
_MAX_CRF = {'h264': 51, 'hevc': 51, 'av1': 63, 'vp9': 63}

# --- from backend/src/core/telemetry.py ---
_ENV_VAR = 'IMAGE_TOOLKIT_TELEMETRY'
TELEMETRY_DIR = Path.home() / '.image-toolkit' / 'telemetry'
_TRUTHY = {'1', 'true', 'yes', 'on'}
NATIVE_SCAN_LOCK = threading.Lock()
NATIVE_IMAGE_BATCH_LOCK = threading.Lock()

# --- from backend/src/core/phash_deduplicator.py ---
CORE__IMG_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif', '.gif'}
DEFAULT_PHASH_THRESHOLD = 10

# --- from backend/src/core/lifecycle_memory.py ---
LIFECYCLE_RSS_ALERT_MB: float = float(os.environ.get('LIFECYCLE_RSS_ALERT_MB', '200'))
_HISTORY: List[Dict] = []

# --- from backend/src/core/cbir_search.py ---
_INDEX_FILE = 'clip_index.faiss'
_PATHS_FILE = 'clip_paths.json'
_CLIP_MODEL_NAME = 'clip-ViT-B-32'

# --- from backend/src/core/dir_phash_index.py ---
CORE_DIR_PHASH_INDEX__IMG_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif', '.gif')
_U64 = 18446744073709551615

# --- from backend/src/core/similarity/embedder.py ---
_ACTIVE: Dict[str, 'BaseEmbedder'] = {}

# --- from backend/src/core/similarity/triage.py ---
_FORMAT_RANK = {'.png': 1.0, '.tiff': 1.0, '.tif': 1.0, '.bmp': 0.9, '.webp': 0.7, '.jpg': 0.4, '.jpeg': 0.4, '.gif': 0.3}

# --- from backend/src/core/similarity/config.py ---
SIMILARITY_DEFAULT_CACHE_PATH = os.path.join(os.path.expanduser('~'), '.image-toolkit', 'similarity_cache.db')
EMBED_MODELS = ['mobileclip', 'openclip', 'resnet18']

# --- from backend/src/core/similarity/cache.py ---
SIMILARITY__SCHEMA = '\nCREATE TABLE IF NOT EXISTS file_index (\n    filepath            TEXT PRIMARY KEY,\n    modified_timestamp  REAL NOT NULL,\n    file_size           INTEGER NOT NULL,\n    xxh64               TEXT,\n    hash_size           INTEGER,\n    phash               TEXT,\n    dhash               TEXT,\n    whash               TEXT,\n    embed_model         TEXT,\n    embedding           BLOB\n);\nCREATE INDEX IF NOT EXISTS idx_file_index_xxh64 ON file_index (xxh64);\n'

# --- from backend/src/core/wallpaper/_dbus.py ---
_QDBUS_CANDIDATES = ['qdbus6', 'qdbus-qt6', 'qdbus', 'qdbus-qt5']

# --- from backend/src/core/wallpaper/_windows.py ---
IDESKTOPWALLPAPER_IID = '{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}'
DESKTOPWALLPAPER_CLSID = '{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}'
COM_AVAILABLE = False

# --- from backend/src/core/image_merger/_models.py ---
IMAGE_MERGER__BIREFNET_OK: bool = _importlib_util_merger.find_spec('transformers') is not None
_LOFTR_OK: bool = _importlib_util_merger.find_spec('kornia') is not None
