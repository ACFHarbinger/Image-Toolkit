"""Official MyAnimeList API v2 client (alternative to jikan_client.py).

Unlike Jikan (a third-party caching proxy that scrapes MAL and can fail when
its cache misses -- see jikan_client.py), this hits MAL's own API directly.
It only needs a free Client ID (no OAuth/user login) for the read-only public
endpoints used here: https://myanimelist.net/apiconfig -> create an app.

Trade-off: the official API does not expose characters/staff/voice-actor
data on any public read-only endpoint, so those fields are always empty here
(characters_available is always False) -- callers already treat that as
"data unavailable" (see jikan_client.py's own 18+-content fallback for the
same shape).
"""

import requests

from backend.src.web.search_engines.common import resolve_api_key

_API_ROOT = "https://api.myanimelist.net/v2"

_STATUS_MAP = {
    "finished_airing": "Completed",
    "currently_airing": "Watching / Reading",
    "not_yet_aired": "Plan to Watch",
}

_ANIME_FIELDS = (
    "synopsis,mean,num_episodes,status,genres,start_season,studios"
)


def _client_id(explicit: str | None = None) -> str | None:
    return resolve_api_key(
        "myanimelist", "MAL_CLIENT_ID", explicit=explicit, field="client_id"
    )


def fetch_mal_anime_data(title: str, client_id: str | None = None) -> dict:
    """Query the official MAL API v2 for the top anime matching *title*.

    Returns the same dict shape as jikan_client.fetch_mal_anime_data(), with
    characters/voice_actors/staff always empty (not available via this API).
    On failure returns {"error": "<message>"}.
    """
    resolved_client_id = _client_id(client_id)
    if not resolved_client_id:
        return {
            "error": (
                "Official MAL API selected but no client ID is configured. "
                "Set MAL_CLIENT_ID or backend/config/api_keys.yaml "
                "[myanimelist].client_id (free, see api_keys.yaml.example)."
            )
        }

    headers = {"X-MAL-CLIENT-ID": resolved_client_id}
    try:
        search_resp = requests.get(
            f"{_API_ROOT}/anime",
            params={"q": title, "limit": 1},
            headers=headers,
            timeout=10,
        )
        if not search_resp.ok:
            return {
                "error": (
                    f"MAL API error {search_resp.status_code} for '{title}': "
                    f"{search_resp.text[:200]}"
                )
            }
        results = search_resp.json().get("data", [])
        if not results:
            return {"error": f"No results found for '{title}' on MyAnimeList."}

        anime_id = results[0]["node"]["id"]

        detail_resp = requests.get(
            f"{_API_ROOT}/anime/{anime_id}",
            params={"fields": _ANIME_FIELDS},
            headers=headers,
            timeout=10,
        )
        if not detail_resp.ok:
            return {
                "error": (
                    f"MAL API error {detail_resp.status_code} fetching "
                    f"details for '{title}': {detail_resp.text[:200]}"
                )
            }
        anime = detail_resp.json()

        genres = ", ".join(g["name"] for g in anime.get("genres", []))
        score = anime.get("mean")
        year = (anime.get("start_season") or {}).get("year") or 0
        studios = [s["name"] for s in anime.get("studios", []) if s.get("name")]

        return {
            "synopsis": anime.get("synopsis", ""),
            "episodes": anime.get("num_episodes") or 1,
            "score": float(score) if score else 0.0,
            "status": _STATUS_MAP.get(anime.get("status", ""), ""),
            "genres": genres,
            "year": int(year) if year else 0,
            "mal_url": f"https://myanimelist.net/anime/{anime_id}",
            "studios": studios,
            "producers": [],
            "characters": [],
            "voice_actors": [],
            "staff": [],
            "characters_available": False,
        }
    except requests.RequestException as exc:
        return {"error": f"Network error: {exc}"}
    except Exception as exc:
        return {"error": f"Failed to parse MAL API response: {exc}"}
