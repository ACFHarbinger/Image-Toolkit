import time

import requests

_STATUS_MAP = {
    "Finished Airing": "Completed",
    "Currently Airing": "Watching / Reading",
    "Not yet aired": "Plan to Watch",
}


def _normalize_name(name: str) -> str:
    """Convert 'Last, First' (Jikan format) → 'First Last' for entity matching."""
    if ", " in name:
        last, first = name.split(", ", 1)
        return f"{first} {last}"
    return name


def _jikan_get(url: str, **params) -> dict | None:
    """Rate-limited Jikan GET.

    Returns the parsed JSON dict, or *None* if the server returns an error
    status (e.g. 404 / 500 for adult-content restricted endpoints).
    Never raises for HTTP errors — callers treat None as "no data available".
    """
    time.sleep(0.4)  # respect ≈3 req/s public rate limit
    try:
        resp = requests.get(url, params=params, timeout=10)
    except requests.RequestException:
        return None
    if not resp.ok:  # 4xx / 5xx — common for 18+ content on /characters
        return None
    try:
        return resp.json()
    except Exception:
        return None


def fetch_mal_anime_data(title: str) -> dict:
    """Query Jikan v4 for the top anime matching *title*.

    Returns a dict with metadata fields plus entity lists for auto-association:
      studios, producers, characters, voice_actors, staff,
      characters_available (bool — False when Jikan blocks the endpoint).

    On failure returns {"error": "<message>"}.
    """
    try:
        resp = requests.get(
            "https://api.jikan.moe/v4/anime",
            params={"q": title, "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("data", [])
        if not results:
            return {"error": f"No results found for '{title}' on MyAnimeList."}

        anime = results[0]
        mal_id = anime.get("mal_id")
        genres = ", ".join(g["name"] for g in anime.get("genres", []))
        score = anime.get("score")
        year = anime.get("year") or (
            anime.get("aired", {}).get("prop", {}).get("from", {}).get("year") or 0
        )

        # Studios / producers — available on the main endpoint (always works)
        studios = [s["name"] for s in anime.get("studios", []) if s.get("name")]
        producers = [p["name"] for p in anime.get("producers", []) if p.get("name")]

        # Characters + voice actors — may be unavailable for 18+ content
        characters: list[str] = []
        voice_actors: list[str] = []
        characters_available = False

        if mal_id:
            char_data = _jikan_get(
                f"https://api.jikan.moe/v4/anime/{mal_id}/characters"
            )
            if char_data is not None:
                characters_available = True
                for entry in char_data.get("data", []):
                    char_name = entry.get("character", {}).get("name", "")
                    if char_name:
                        characters.append(_normalize_name(char_name))
                    for va in entry.get("voice_actors", []):
                        if va.get("language") == "Japanese":
                            va_name = va.get("person", {}).get("name", "")
                            if va_name:
                                voice_actors.append(_normalize_name(va_name))

        # Staff — usually available regardless of content rating
        staff: list[dict] = []
        if mal_id:
            staff_data = _jikan_get(
                f"https://api.jikan.moe/v4/anime/{mal_id}/staff"
            )
            if staff_data is not None:
                for entry in staff_data.get("data", []):
                    person_name = entry.get("person", {}).get("name", "")
                    positions = entry.get("positions", [])
                    if person_name:
                        staff.append(
                            {
                                "name": _normalize_name(person_name),
                                "positions": positions,
                            }
                        )

        return {
            "synopsis": anime.get("synopsis", ""),
            "episodes": anime.get("episodes") or 1,
            "score": float(score) if score else 0.0,
            "status": _STATUS_MAP.get(anime.get("status", ""), ""),
            "genres": genres,
            "year": int(year) if year else 0,
            "mal_url": anime.get("url", ""),
            # Entity lists for auto-association
            "studios": studios,
            "producers": producers,
            "characters": characters,
            "voice_actors": voice_actors,
            "staff": staff,
            "characters_available": characters_available,
        }
    except requests.RequestException as exc:
        return {"error": f"Network error: {exc}"}
    except Exception as exc:
        return {"error": f"Failed to parse Jikan response: {exc}"}
