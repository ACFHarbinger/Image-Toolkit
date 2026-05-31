import requests


_STATUS_MAP = {
    "Finished Airing": "Completed",
    "Currently Airing": "Watching / Reading",
    "Not yet aired": "Plan to Watch",
}


def fetch_mal_anime_data(title: str) -> dict:
    """Query Jikan v4 for the top anime result matching *title*.

    Returns a dict with keys: synopsis, episodes, score, status, genres, year.
    On failure, returns {"error": "<message>"}.
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
        genres = ", ".join(g["name"] for g in anime.get("genres", []))
        score = anime.get("score")
        year = anime.get("year") or (
            anime.get("aired", {}).get("prop", {}).get("from", {}).get("year") or 0
        )
        mal_status = anime.get("status", "")
        return {
            "synopsis": anime.get("synopsis", ""),
            "episodes": anime.get("episodes") or 1,
            "score": int(round(score)) if score else 0,
            "status": _STATUS_MAP.get(mal_status, ""),
            "genres": genres,
            "year": int(year) if year else 0,
        }
    except requests.RequestException as exc:
        return {"error": f"Network error: {exc}"}
    except Exception as exc:
        return {"error": f"Failed to parse Jikan response: {exc}"}
