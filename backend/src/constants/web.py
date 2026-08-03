# Reverse-image-search / web-crawler engine identifiers.
#
# Previously redeclared identically (same string values) in five separate
# files (reverse_image_search_crawler.py, search_engines/__init__.py, and
# each individual strategy module) since the strategy modules can't import
# from reverse_image_search_crawler without a circular import (the crawler
# imports the strategies). Centralizing here removes the duplication and
# the circular-import constraint that caused it.
ENGINE_GOOGLE = "google"
ENGINE_TINEYE = "tineye"
ENGINE_LOCAL_CBIR = "local_cbir"
ENGINE_BING = "bing"
ENGINE_YANDEX = "yandex"
ENGINE_SAUCENAO = "saucenao"
ENGINE_IQDB = "iqdb"
ENGINE_SUBREDDIT_SWEEP = "subreddit_sweep"

SUPPORTED_ENGINES = (
    ENGINE_GOOGLE, ENGINE_TINEYE, ENGINE_LOCAL_CBIR,
    ENGINE_BING, ENGINE_YANDEX, ENGINE_SAUCENAO, ENGINE_IQDB,
)

import os
import re

# --- from backend/src/web/subreddit_phash_sweep.py ---
_IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
_HASH_SIZE = 8
_MAX_BITS = _HASH_SIZE * _HASH_SIZE

# --- from backend/src/web/search_engines/yandex_strategy.py ---
_UPLOAD_URL = 'https://yandex.com/images-apphost/image-download'
_SEARCH_URL = 'https://yandex.com/images/search'
_CAPTCHA_MARKERS = ('showcaptcha', 'SmartCaptcha', 'captcha')
_RES_RE = re.compile('(\\d+)\\s*[×x]\\s*(\\d+)')

# --- from backend/src/web/search_engines/iqdb_strategy.py ---
SEARCH_ENGINES__SEARCH_URL = 'https://iqdb.org/'
_SIM_RE = re.compile('(\\d+)%\\s*similarity', re.IGNORECASE)
SEARCH_ENGINES__RES_RE = re.compile('(\\d+)[×x](\\d+)')

# --- from backend/src/web/search_engines/bing_visual_strategy.py ---
_API_ENDPOINT = 'https://api.bing.microsoft.com/v7.0/images/visualsearch'
_SBI_UPLOAD = 'https://www.bing.com/images/search?view=detailv2&iss=sbi&FORM=SBIIRP'
SEARCH_ENGINES_BING_VISUAL_STRATEGY__RES_RE = re.compile('"width":(\\d+),"height":(\\d+)')

# --- from backend/src/web/search_engines/saucenao_strategy.py ---
_API_BASE = 'https://saucenao.com/search.php'

# --- from backend/src/web/search_engines/common.py ---
DEFAULT_USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0'
_RATE_LIMIT_STATUS = {429, 503}

# --- from backend/src/web/clients/jikan_client.py ---
_STATUS_MAP = {'Finished Airing': 'Completed', 'Currently Airing': 'Watching / Reading', 'Not yet aired': 'Plan to Watch'}
_RETRY_STATUS_CODES = {429, 502, 503, 504}
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.5

# --- from backend/src/web/clients/tineye_client.py ---
CLIENTS__API_BASE = 'https://api.tineye.com/rest/'
_SEARCH_ENDPOINT = f'{_API_BASE}search/'
_DEFAULT_TIMEOUT = 30
CLIENTS__MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0

# --- from backend/src/web/clients/mal_dispatcher.py ---
_DEFAULT_METHOD = 'jikan'

# --- from backend/src/web/clients/mal_api_client.py ---
_API_ROOT = 'https://api.myanimelist.net/v2'
CLIENTS__STATUS_MAP = {'finished_airing': 'Completed', 'currently_airing': 'Watching / Reading', 'not_yet_aired': 'Plan to Watch'}
_ANIME_FIELDS = 'synopsis,mean,num_episodes,status,genres,start_season,studios'

# --- from backend/src/web/clients/mal_scrape_client.py ---
CLIENTS__SEARCH_URL = 'https://myanimelist.net/anime.php'
_ANIME_URL_RE = re.compile('https://myanimelist\\.net/anime/(\\d+)/([^/?#]+)/?$')
CLIENTS_MAL_SCRAPE_CLIENT__STATUS_MAP = {'Finished Airing': 'Completed', 'Currently Airing': 'Watching / Reading', 'Not yet aired': 'Plan to Watch'}
_REQUEST_DELAY_SECONDS = 0.6

# --- from backend/src/web/downloaders/reddit_downloader.py ---
DOWNLOADERS__IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
_DIRECT_HOSTS = ('i.redd.it', 'i.imgur.com')

# --- from backend/src/web/downloaders/nhentai_downloader.py ---
_GALLERY_ID_RE = re.compile('(\\d+)')
_SVELTEKIT_JSON_RE = re.compile('<script type="application/json" data-sveltekit-fetched data-url="/api/v2/galleries/\\d+[^"]*">(.*?)</script>', re.DOTALL)
_LEGACY_GALLERY_JSON_RE = re.compile('window\\._gallery\\s*=\\s*JSON\\.parse\\(\\"(.*?)\\"\\);', re.DOTALL)
_DEFAULT_HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
_PAGE_EXT = {'j': '.jpg', 'p': '.png', 'g': '.gif', 'w': '.webp'}

# --- from backend/src/web/recon/embedder.py ---
_FACE_APP = {'app': None, 'tried': False}

# --- from backend/src/web/recon/consensus.py ---
_NER = {'model': None, 'kind': None, 'tried': False}
_NAME_RE = re.compile('\\b([A-Z][a-z]{1,20}(?:\\s+[A-Z][a-z]{1,20}){1,2})\\b')
_STOP = {'The Best', 'New York', 'United States', 'Sign In', 'Log In', 'Home Page', 'Privacy Policy', 'Terms Of', 'All Rights', 'Read More', 'Search Results'}

# --- from backend/src/web/recon/dispatcher.py ---
_SCHEMA = '\nCREATE TABLE IF NOT EXISTS provenance_cache (\n    cutout_hash TEXT NOT NULL,\n    engine      TEXT NOT NULL,\n    fetched_at  REAL NOT NULL,\n    results     TEXT NOT NULL,\n    PRIMARY KEY (cutout_hash, engine)\n);\n'

# --- from backend/src/web/recon/indexer.py ---
_IMG_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}

# --- from backend/src/web/recon/config.py ---
RECON_HOME = os.path.join(os.path.expanduser('~'), '.image-toolkit', 'recon')
DEFAULT_CACHE_PATH = os.path.join(RECON_HOME, 'provenance_cache.db')
REVERSE_ENGINES = ['google_lens', 'yandex', 'bing', 'saucenao']

# --- from backend/src/web/recon/segmenter.py ---
_SAM = {'model': None, 'predictor': None, 'kind': None}
