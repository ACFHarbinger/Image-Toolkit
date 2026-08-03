"""Reverse-image-search engine strategies beyond the built-in trio.

Each strategy implements the ``ReverseSearchEngine`` interface from
``reverse_image_search_crawler`` so ``MetaSearchDispatcher`` can treat them
uniformly. SauceNao and IQDB talk to real documented interfaces; Bing and
Yandex scrape the public web UI (brittle by nature — they fail soft to an
empty result list or a ``RateLimited`` the dispatcher isolates).
"""

from backend.src.constants import (
    ENGINE_BING as ENGINE_BING,
)
from backend.src.constants import (
    ENGINE_IQDB as ENGINE_IQDB,
)
from backend.src.constants import (
    ENGINE_SAUCENAO as ENGINE_SAUCENAO,
)
from backend.src.constants import (
    ENGINE_YANDEX as ENGINE_YANDEX,
)

from .bing_visual_strategy import BingVisualSearchStrategy as BingVisualSearchStrategy
from .common import RateLimited as RateLimited
from .iqdb_strategy import IqdbStrategy as IqdbStrategy
from .saucenao_strategy import SauceNaoStrategy as SauceNaoStrategy
from .yandex_strategy import YandexSearchStrategy as YandexSearchStrategy

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
