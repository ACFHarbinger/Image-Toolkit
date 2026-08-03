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
