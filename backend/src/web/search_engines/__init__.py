"""Reverse-image-search engine strategies beyond the built-in trio.

Each strategy implements the ``ReverseSearchEngine`` interface from
``reverse_image_search_crawler`` so ``MetaSearchDispatcher`` can treat them
uniformly. SauceNao and IQDB talk to real documented interfaces; Bing and
Yandex scrape the public web UI (brittle by nature — they fail soft to an
empty result list or a ``RateLimited`` the dispatcher isolates).
"""

from .bing_visual_strategy import BingVisualSearchStrategy as BingVisualSearchStrategy
from .common import RateLimited as RateLimited
from .iqdb_strategy import IqdbStrategy as IqdbStrategy
from .saucenao_strategy import SauceNaoStrategy as SauceNaoStrategy
from .yandex_strategy import YandexSearchStrategy as YandexSearchStrategy

ENGINE_BING = "bing"
ENGINE_YANDEX = "yandex"
ENGINE_SAUCENAO = "saucenao"
ENGINE_IQDB = "iqdb"

__all__ = [
    "BingVisualSearchStrategy",
    "IqdbStrategy",
    "RateLimited",
    "SauceNaoStrategy",
    "YandexSearchStrategy",
    "ENGINE_BING",
    "ENGINE_YANDEX",
    "ENGINE_SAUCENAO",
    "ENGINE_IQDB",
]
