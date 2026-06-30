"""TinEye Reverse Image Search API client.

Authentication uses HMAC-SHA256 request signing as per TinEye's commercial API.
Credentials are resolved in priority order:

    1. Environment variables ``TINEYE_API_KEY`` and ``TINEYE_API_SECRET``.
    2. ``backend/config/api_keys.yaml`` (path relative to the project root).

The ``api_keys.yaml`` file is intentionally excluded from version control.
A template is provided at ``backend/config/api_keys.yaml.example``.

Dependencies:
    requests>=2.32.5   (already in pyproject.toml)

References:
    https://services.tineye.com/library/python/
    https://api.tineye.com/rest/
"""

import hashlib
import hmac
import logging
import os
import time
import uuid
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlencode, urlparse

import requests

from backend.src.web.models import ReverseSearchResult

log = logging.getLogger(__name__)

_API_BASE = "https://api.tineye.com/rest/"
_SEARCH_ENDPOINT = f"{_API_BASE}search/"
_DEFAULT_TIMEOUT = 30
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0  # seconds


def _load_credentials() -> tuple[str, str]:
    """Resolve TinEye API credentials from env or config file.

    Returns:
        A ``(api_key, api_secret)`` tuple.

    Raises:
        EnvironmentError: When no credentials can be found.
    """
    api_key = os.environ.get("TINEYE_API_KEY", "").strip()
    api_secret = os.environ.get("TINEYE_API_SECRET", "").strip()

    if api_key and api_secret:
        return api_key, api_secret

    # Locate project root relative to this file (backend/src/web/clients/)
    config_path = Path(__file__).parents[4] / "backend" / "config" / "api_keys.yaml"
    if config_path.is_file():
        try:
            import yaml  # type: ignore[import-untyped]

            with open(config_path, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
            tineye_cfg = cfg.get("tineye", {})
            api_key = api_key or str(tineye_cfg.get("api_key", "")).strip()
            api_secret = api_secret or str(tineye_cfg.get("api_secret", "")).strip()
        except Exception as exc:
            log.warning("Could not parse %s: %s", config_path, exc)

    if not api_key or not api_secret:
        raise EnvironmentError(
            "TinEye credentials not found.\n"
            "Set TINEYE_API_KEY and TINEYE_API_SECRET environment variables, or\n"
            f"provide 'tineye.api_key' / 'tineye.api_secret' in {config_path}."
        )
    return api_key, api_secret


class TinEyeClient:
    """Wrapper around the TinEye commercial API.

    Args:
        api_key: TinEye API public key.  Resolved from environment if omitted.
        api_secret: TinEye API secret.  Resolved from environment if omitted.
        timeout: Per-request timeout in seconds.

    Raises:
        EnvironmentError: If credentials cannot be resolved and none are passed.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        if api_key and api_secret:
            self._key = api_key
            self._secret = api_secret
        else:
            self._key, self._secret = _load_credentials()
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "ImageToolkit/1.0 TinEyeClient"})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_by_file(
        self,
        image_path: str,
        offset: int = 0,
        limit: int = 20,
    ) -> List[ReverseSearchResult]:
        """Upload *image_path* and search TinEye for matches.

        Args:
            image_path: Absolute path to the local image file.
            offset: Result pagination offset.
            limit: Maximum number of results (TinEye max is 150).

        Returns:
            Sorted list of :class:`~backend.src.web.models.ReverseSearchResult`,
            highest confidence first.  Empty on failure.
        """
        params = self._build_params(
            method="search",
            extra={"offset": offset, "limit": limit},
        )
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                with open(image_path, "rb") as fh:
                    resp = self._session.post(
                        _SEARCH_ENDPOINT,
                        params=params,
                        files={"image": (Path(image_path).name, fh, "image/jpeg")},
                        timeout=self._timeout,
                    )
                if resp.status_code == 429:
                    wait = _RETRY_BACKOFF_BASE ** attempt
                    log.warning("TinEye rate limit hit; retrying in %.1fs…", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return self._parse_response(resp.json())
            except requests.exceptions.Timeout:
                log.warning(
                    "TinEye request timed out (attempt %d/%d).", attempt, _MAX_RETRIES
                )
                if attempt == _MAX_RETRIES:
                    raise
                time.sleep(_RETRY_BACKOFF_BASE * attempt)
            except requests.exceptions.RequestException as exc:
                log.error("TinEye request failed: %s", exc)
                raise
        return []

    def search_by_url(
        self,
        image_url: str,
        offset: int = 0,
        limit: int = 20,
    ) -> List[ReverseSearchResult]:
        """Search TinEye using a publicly accessible *image_url*.

        Args:
            image_url: Direct URL to the image.
            offset: Result pagination offset.
            limit: Maximum number of results.

        Returns:
            Sorted list of :class:`~backend.src.web.models.ReverseSearchResult`.
        """
        params = self._build_params(
            method="search",
            extra={"image_url": image_url, "offset": offset, "limit": limit},
        )
        resp = self._session.get(
            _SEARCH_ENDPOINT, params=params, timeout=self._timeout
        )
        resp.raise_for_status()
        return self._parse_response(resp.json())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_params(self, method: str, extra: dict) -> dict:
        """Build and HMAC-sign the request parameter dict."""
        nonce = uuid.uuid4().hex
        timestamp = int(time.time())

        base_params: dict = {
            "api_key": self._key,
            "date": timestamp,
            "nonce": nonce,
        }
        base_params.update(extra)

        # Signature payload: HTTP_VERB + api_key + date + nonce + method (sorted)
        sorted_params = "&".join(
            f"{k}={v}" for k, v in sorted(base_params.items()) if k != "image_url"
        )
        payload = f"POST\n{self._key}\n{timestamp}\n{nonce}\n{method}\n{sorted_params}"

        sig = hmac.new(
            self._secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        base_params["api_sig"] = sig
        return base_params

    @staticmethod
    def _parse_response(data: dict) -> List[ReverseSearchResult]:
        """Convert the TinEye JSON payload into result objects.

        TinEye response structure::

            {
              "code": 200,
              "matches": [
                {
                  "image_url": "https://...",
                  "width": 1920,
                  "height": 1080,
                  "score": 98.7,
                  ...
                }
              ]
            }
        """
        results: List[ReverseSearchResult] = []
        if data.get("code") != 200:
            log.warning("TinEye returned non-200 code: %s", data.get("code"))
            return results

        for match in data.get("matches", []):
            url = match.get("image_url") or match.get("url", "")
            if not url:
                continue
            w = match.get("width", 0)
            h = match.get("height", 0)
            resolution = f"{w}x{h}" if w and h else "Unknown"
            raw_score = match.get("score", 0.0)
            # TinEye scores are 0-100; normalise to [0, 1]
            score = float(raw_score) / 100.0 if raw_score > 1 else float(raw_score)
            results.append(
                ReverseSearchResult(
                    url=url,
                    engine="tineye",
                    score=score,
                    resolution=resolution,
                    title=urlparse(url).netloc,
                )
            )
        results.sort(key=lambda r: r.score, reverse=True)
        return results
