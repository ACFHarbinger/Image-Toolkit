# SDXL/LoRA target-module lists.
from pathlib import Path
from typing import Callable, Dict, TypeVar

# Previously redeclared identically (byte-for-byte, just reformatted) in four
# separate tuner files: dream_booth_tuner.py, lo_ra_tuner.py,
# lo_ra_tuner_config.py, lo_ra_tuner_v2.py.
SDXL_ATTN_TARGETS = (
    "to_q", "to_k", "to_v", "to_out.0",
    "proj_in", "proj_out",
    "ff.net.0.proj", "ff.net.2",
)
SDXL_CONV_TARGETS = (
    "conv1", "conv2", "conv_shortcut", "conv", "time_emb_proj",
)
TE_ATTN_TARGETS = ("q_proj", "k_proj", "v_proj", "out_proj")

# --- from backend/src/models/wrappers/esrgan_wrapper.py ---
ANIME_6B_FILENAME = 'RealESRGAN_x4plus_anime_6B.pth'

# --- from backend/src/models/wrappers/birefnet_wrapper.py ---
TOONOUT_MODEL = 'joelseytre/toonout'
BIREFNET_MODEL = 'ZhengPeng7/BiRefNet'
_BIREFNET_OK = False
_BIREFNET_ERR = ''

# --- from backend/src/models/wrappers/jamma_wrapper.py ---
_JAMMA_OK = False
_JAMMA_ERR = ''
_HF_REPO = 'leoluxxx/JamMa'
_CKPT_FILE = 'jamma_outdoor.ckpt'
_MIN_INLIERS = 20

# --- from backend/src/models/wrappers/roma_wrapper.py ---
_MAX_DRIFT_RATIO = 0.4

# --- from backend/src/models/wrappers/efficient_loftr_wrapper.py ---
WRAPPERS__HF_REPO = 'zju-community/efficientloftr'
WRAPPERS__MIN_INLIERS = 20

# --- from backend/src/models/wrappers/wd_tagger_wrapper.py ---
_DEFAULT_REPO = 'SmilingWolf/wd-v1-4-convnext-tagger-v2'
_DEFAULT_CACHE = Path.home() / '.image-toolkit' / 'models' / 'wd_tagger'
_CATEGORY_NAMES: Dict[int, str] = {0: 'general', 4: 'character', 9: 'rating'}

# --- from backend/src/models/wrappers/loftr_wrapper.py ---
_LOFTR_H = 320
_LOFTR_W = 448
WRAPPERS_LOFTR_WRAPPER__MIN_INLIERS = 20

# --- from backend/src/models/wrappers/aliked_lg_wrapper.py ---
WRAPPERS_ALIKED_LG_WRAPPER__MIN_INLIERS = 15

# --- from backend/src/models/data/lora_dataset.py ---
SDXL_BUCKETS: tuple[tuple[int, int], ...] = ((1024, 1024), (1152, 896), (896, 1152), (1216, 832), (832, 1216), (1344, 768), (768, 1344), (1536, 640), (640, 1536), (1280, 768), (768, 1280), (1408, 704), (704, 1408))

# --- from backend/src/models/data/captioner.py ---
_DEFAULT_UNDESIRED = frozenset({'watermark', 'signature', 'artist name', 'logo', 'text', 'copyright name', 'censored', 'bar censor'})

# --- from backend/src/models/data/cbir_dataset.py ---
_IMG_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}

# --- from backend/src/models/tuning/cbir_index_builder.py ---
_BATCH_SIZE = 64

# --- from backend/src/models/core/comfy_manager.py ---
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8188

# --- from backend/src/models/core/base.py ---
_F = TypeVar('_F', bound=Callable)
