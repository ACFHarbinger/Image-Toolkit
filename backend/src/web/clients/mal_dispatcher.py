"""Picks which MAL data-fetch client to use for "Auto-Fill from MAL".

Three interchangeable clients exist, each returning the same dict shape
(see jikan_client.fetch_mal_anime_data docstring) and each with distinct
failure modes:

- "jikan": jikan_client.py -- default, richest data (characters/staff always
  attempted), but is a third-party cache/proxy that can 504 when its cache
  misses MAL live, independent of MAL's own health.
- "official_api": mal_api_client.py -- hits MAL's own API v2 directly, needs
  a free client ID (Settings > api_keys.yaml), but has no characters/staff.
- "scrape": mal_scrape_client.py -- scrapes myanimelist.net directly, no
  key needed, has full data, but is slower (2-3 sequential page loads) and
  more fragile to MAL markup changes.
"""

from backend.src.web.clients import jikan_client, mal_api_client, mal_scrape_client

# (internal key, human-readable label for Settings UI), in display order.
MAL_FETCH_METHODS = (
    ("jikan", "Jikan API (Default)"),
    ("official_api", "Official MyAnimeList API"),
    ("scrape", "Direct Website Scraping"),
)
_DEFAULT_METHOD = "jikan"

_DISPATCH = {
    "jikan": jikan_client.fetch_mal_anime_data,
    "official_api": mal_api_client.fetch_mal_anime_data,
    "scrape": mal_scrape_client.fetch_mal_anime_data,
}


def fetch_mal_anime_data(title: str, method: str = _DEFAULT_METHOD) -> dict:
    """Fetch MAL anime data for *title* using the given *method*.

    Falls back to the default ("jikan") for an unrecognized method rather
    than raising, since *method* usually comes straight from a persisted
    setting that could be stale/corrupted.
    """
    fetch_fn = _DISPATCH.get(method, _DISPATCH[_DEFAULT_METHOD])
    return fetch_fn(title)
