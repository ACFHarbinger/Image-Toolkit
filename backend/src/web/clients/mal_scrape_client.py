"""Direct MyAnimeList page scraper (alternative to jikan_client.py).

Bypasses Jikan (a third-party proxy that can fail independently of MAL
itself -- see jikan_client.py) by scraping myanimelist.net directly: a
search page for the title, then the anime's own detail + characters pages.
No API key/client ID needed, but slower (2-3 sequential page fetches) and
more fragile (breaks if MAL changes its page markup).

Uses backend/src/web/search_engines/common.py's make_session()/
raise_for_rate_limit() helpers, the same pattern the reverse-image-search
engines use for polite scraping (realistic desktop User-Agent, 429/503/403
mapped to typed exceptions).
"""

import re
import time

import requests
from bs4 import BeautifulSoup

from backend.src.web.search_engines.common import (
    EngineBlocked,
    RateLimited,
    make_session,
    raise_for_rate_limit,
)

_SEARCH_URL = "https://myanimelist.net/anime.php"
_ANIME_URL_RE = re.compile(r"https://myanimelist\.net/anime/(\d+)/([^/?#]+)/?$")

_STATUS_MAP = {
    "Finished Airing": "Completed",
    "Currently Airing": "Watching / Reading",
    "Not yet aired": "Plan to Watch",
}

# Politeness delay between sequential page fetches for a single lookup.
_REQUEST_DELAY_SECONDS = 0.6


def _normalize_name(name: str) -> str:
    """Convert 'Last, First' (MAL format) → 'First Last' for entity matching."""
    if ", " in name:
        last, first = name.split(", ", 1)
        return f"{first} {last}"
    return name


def _find_first_result(html: str) -> tuple[str, str] | None:
    """Return (anime_id, slug) for the first search-result link, or None."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    for a in soup.select('a[href*="/anime/"]'):
        m = _ANIME_URL_RE.match(a.get("href", ""))
        if m and m.group(1) not in seen:
            return m.group(1), m.group(2)
        if m:
            seen.add(m.group(1))
    return None


def _parse_detail_page(html: str, anime_id: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    desc_el = soup.find("p", itemprop="description") or soup.find(
        "span", itemprop="description"
    )
    synopsis = desc_el.get_text(strip=True) if desc_el else ""

    score_el = soup.find(itemprop="ratingValue")
    score = score_el.get_text(strip=True) if score_el else None

    genres = [g.get_text(strip=True) for g in soup.find_all("span", itemprop="genre")]

    sidebar = {}
    for div in soup.find_all("div", class_="spaceit_pad"):
        text = div.get_text(" ", strip=True)
        if ":" in text:
            label, _, value = text.partition(":")
            sidebar.setdefault(label.strip(), value.strip())

    episodes_raw = sidebar.get("Episodes", "")
    episodes = int(episodes_raw) if episodes_raw.isdigit() else 1

    status = _STATUS_MAP.get(sidebar.get("Status", ""), "")

    year = 0
    aired = sidebar.get("Aired", "")
    year_match = re.search(r"\b(19|20)\d{2}\b", aired)
    if year_match:
        year = int(year_match.group(0))

    studios = [s.strip() for s in sidebar.get("Studios", "").split(",") if s.strip()]
    producers = [
        p.strip() for p in sidebar.get("Producers", "").split(",") if p.strip()
    ]

    return {
        "synopsis": synopsis,
        "episodes": episodes,
        "score": float(score) if score else 0.0,
        "status": status,
        "genres": ", ".join(genres),
        "year": year,
        "mal_url": f"https://myanimelist.net/anime/{anime_id}",
        "studios": studios,
        "producers": producers,
    }


def _parse_characters_page(html: str) -> tuple[list[str], list[str], list[dict]]:
    """Returns (characters, japanese_voice_actors, staff)."""
    soup = BeautifulSoup(html, "html.parser")

    characters: list[str] = []
    voice_actors: list[str] = []
    for char_table in soup.select("table.js-anime-character-table"):
        name_el = char_table.select_one("h3.h3_character_name")
        if name_el:
            char_name = name_el.get_text(strip=True)
            if char_name:
                characters.append(_normalize_name(char_name))
        for va_row in char_table.select("tr.js-anime-character-va-lang"):
            lang_el = va_row.select_one(".js-anime-character-language")
            if not lang_el or lang_el.get_text(strip=True) != "Japanese":
                continue
            va_link = va_row.find("a", href=lambda h: h and "/people/" in h)
            if va_link:
                va_name = va_link.get_text(strip=True)
                if va_name:
                    voice_actors.append(_normalize_name(va_name))

    staff: list[dict] = []
    staff_heading = next(
        (h for h in soup.find_all("h2") if h.get_text(strip=True) == "Staff"), None
    )
    if staff_heading is not None:
        first_table = staff_heading.find_next("table")
        if first_table is not None:
            for table in [first_table, *first_table.find_next_siblings("table")]:
                name_link = next(
                    (
                        a
                        for a in table.find_all(
                            "a", href=lambda h: h and "/people/" in h
                        )
                        if a.find("img") is None
                    ),
                    None,
                )
                small = table.find("small")
                if name_link is None or small is None:
                    continue
                person_name = name_link.get_text(strip=True)
                positions = [p.strip() for p in small.get_text(strip=True).split(",")]
                if person_name:
                    staff.append(
                        {"name": _normalize_name(person_name), "positions": positions}
                    )

    return characters, voice_actors, staff


def fetch_mal_anime_data(title: str) -> dict:
    """Scrape myanimelist.net directly for the top anime matching *title*.

    Returns the same dict shape as jikan_client.fetch_mal_anime_data().
    On failure returns {"error": "<message>"}.
    """
    session = make_session()
    try:
        search_resp = session.get(_SEARCH_URL, params={"q": title, "cat": "anime"}, timeout=15)
        raise_for_rate_limit(search_resp, "myanimelist")
        search_resp.raise_for_status()

        match = _find_first_result(search_resp.text)
        if match is None:
            return {"error": f"No results found for '{title}' on MyAnimeList."}
        anime_id, slug = match

        time.sleep(_REQUEST_DELAY_SECONDS)
        detail_resp = session.get(
            f"https://myanimelist.net/anime/{anime_id}/{slug}", timeout=15
        )
        raise_for_rate_limit(detail_resp, "myanimelist")
        detail_resp.raise_for_status()
        data = _parse_detail_page(detail_resp.text, anime_id)

        characters: list[str] = []
        voice_actors: list[str] = []
        staff: list[dict] = []
        characters_available = False
        try:
            time.sleep(_REQUEST_DELAY_SECONDS)
            char_resp = session.get(
                f"https://myanimelist.net/anime/{anime_id}/{slug}/characters",
                timeout=15,
            )
            if char_resp.ok:
                characters_available = True
                characters, voice_actors, staff = _parse_characters_page(
                    char_resp.text
                )
        except requests.RequestException:
            pass  # characters/staff are best-effort, main metadata already fetched

        data.update(
            {
                "characters": characters,
                "voice_actors": voice_actors,
                "staff": staff,
                "characters_available": characters_available,
            }
        )
        return data
    except (RateLimited, EngineBlocked) as exc:
        return {"error": f"MyAnimeList {exc}"}
    except requests.RequestException as exc:
        return {"error": f"Network error: {exc}"}
    except Exception as exc:
        return {"error": f"Failed to parse MyAnimeList page: {exc}"}
    finally:
        session.close()
