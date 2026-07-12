"""Shared helpers for reverse-search engine strategies.

Credential resolution mirrors ``tineye_client._load_credentials`` (env first,
then ``backend/config/api_keys.yaml``). A shared ``requests.Session`` factory
sets a realistic desktop User-Agent, and ``raise_for_rate_limit`` maps 429 /
503 into a ``RateLimited`` the dispatcher isolates per engine.
"""

import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# A realistic desktop UA — engines block obvious bot agents outright.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0"
)

_RATE_LIMIT_STATUS = {429, 503}


class RateLimited(RuntimeError):
    """Raised when an engine rate-limits/blocks us; dispatcher-isolated."""


class EngineBlocked(RuntimeError):
    """Raised when an engine returns a hard block (403/CAPTCHA challenge)."""


def resolve_api_key(
    engine: str, env_var: str, explicit: Optional[str] = None, field: str = "api_key"
) -> Optional[str]:
    """Resolve a credential: explicit arg → env var → api_keys.yaml[engine][field].

    *field* defaults to "api_key" but can be e.g. "client_id" for engines
    (Reddit, MyAnimeList) whose credential isn't a single opaque key.

    Returns None when nothing is configured (engines that can run keyless, like
    SauceNao's public tier or IQDB, treat None as "anonymous").
    """
    if explicit:
        return explicit.strip()
    env = os.environ.get(env_var, "").strip()
    if env:
        return env

    config_path = Path(__file__).parents[4] / "backend" / "config" / "api_keys.yaml"
    if config_path.is_file():
        try:
            import yaml

            with open(config_path, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
            section = cfg.get(engine, {}) or {}
            key = str(section.get(field, "")).strip()
            if key:
                return key
        except Exception as exc:
            log.warning("Could not parse %s: %s", config_path, exc)
    return None


def make_session(timeout: float = 20.0):
    """Create a configured ``requests.Session`` (lazy import so import-time is
    cheap and ``requests`` stays an optional dependency for test collection)."""
    import requests

    session = requests.Session()
    session.headers.update({
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
    })
    session.request_timeout = timeout  # convenience attr; requests ignores it
    return session


def raise_for_rate_limit(response, engine: str) -> None:
    """Convert throttle/block HTTP statuses into typed exceptions."""
    if response.status_code in _RATE_LIMIT_STATUS:
        raise RateLimited(f"{engine} rate-limited (HTTP {response.status_code})")
    if response.status_code == 403:
        raise EngineBlocked(f"{engine} blocked the request (HTTP 403)")
