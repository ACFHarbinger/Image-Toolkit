"""Async subreddit sweep with perceptual-hash fast-path matching.

Scrapes recent image submissions from a target subreddit via asyncpraw,
computes a perceptual hash for each via the C++ ``base.similarity`` engine
(``phash_bytes`` / ``batch_hamming`` — the replacement for the original Rust
``phash_engine``), and compares against the query image's hash — bypassing
web-based reverse search entirely for near-instant matches against a known
community.

``asyncpraw`` is imported lazily so the module (and its tests) import without
Reddit credentials or the optional dependency present.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

from backend.src.web.models import ReverseSearchResult

log = logging.getLogger(__name__)

ENGINE_SUBREDDIT_SWEEP = "subreddit_sweep"

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")
_HASH_SIZE = 8          # 64-bit pHash; thresholds below are calibrated for it
_MAX_BITS = _HASH_SIZE * _HASH_SIZE


@dataclass
class SubredditSweepConfig:
    subreddit: str
    post_limit: int = 500
    hamming_threshold: int = 8
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    user_agent: str = "image-toolkit/1.0 (subreddit sweep)"
    download_timeout: float = 15.0


class SubredditPHashSweep:
    """Sweeps a subreddit's recent image posts and pHash-matches a query image."""

    def __init__(
        self,
        config: SubredditSweepConfig,
        status_callback: Optional[callable] = None,
    ) -> None:
        self._config = config
        self._status_callback = status_callback
        self._reddit = None
        self._http = None
        self._is_running = True

    def stop(self) -> None:
        self._is_running = False

    async def sweep(self, query_image_path: str) -> List[ReverseSearchResult]:
        """Fetch posts, hash them, compare, return matches (best first)."""
        import base

        query_hash = await self._hash_query_image(query_image_path)
        if not query_hash:
            self._emit_status("Could not hash the query image.")
            return []

        await self._ensure_clients()
        # Gather (submission, candidate_hash) then batch-compare in one C++ call.
        submissions = []
        hashes = []
        count = 0
        try:
            async for submission in self._iter_image_submissions():
                if not self._is_running:
                    break
                candidate = await self._hash_submission_image(submission)
                if candidate:
                    submissions.append(submission)
                    hashes.append(candidate)
                count += 1
                if count % 25 == 0:
                    self._emit_status(f"Hashed {count} posts…")
        finally:
            await self._close_clients()

        matches: List[ReverseSearchResult] = []
        for idx, distance in base.similarity.batch_hamming(query_hash, hashes):
            if distance <= self._config.hamming_threshold:
                matches.append(self._to_result(submissions[idx], distance))
        matches.sort(key=lambda r: r.score, reverse=True)
        self._emit_status(f"Sweep complete: {len(matches)} matches in {count} posts.")
        return matches

    # ------------------------------------------------------------------
    # Clients
    # ------------------------------------------------------------------

    async def _ensure_clients(self) -> None:
        import aiohttp

        if self._http is None:
            self._http = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._config.download_timeout)
            )
        if self._reddit is None:
            import asyncpraw  # lazy — optional dependency

            client_id = self._config.client_id or os.environ.get("REDDIT_CLIENT_ID")
            client_secret = self._config.client_secret or os.environ.get(
                "REDDIT_CLIENT_SECRET"
            )
            if not client_id or not client_secret:
                raise EnvironmentError(
                    "Reddit API credentials not found. Set REDDIT_CLIENT_ID and "
                    "REDDIT_CLIENT_SECRET (or pass them in SubredditSweepConfig)."
                )
            self._reddit = asyncpraw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=self._config.user_agent,
            )

    async def _close_clients(self) -> None:
        if self._http is not None:
            await self._http.close()
            self._http = None
        if self._reddit is not None:
            await self._reddit.close()
            self._reddit = None

    async def _iter_image_submissions(self):
        subreddit = await self._reddit.subreddit(self._config.subreddit)
        yielded = 0
        async for submission in subreddit.new(limit=self._config.post_limit):
            url = getattr(submission, "url", "") or ""
            hint = getattr(submission, "post_hint", "")
            if hint == "image" or url.lower().endswith(_IMAGE_EXTS):
                yield submission
                yielded += 1
                if yielded >= self._config.post_limit:
                    break

    async def _hash_query_image(self, image_path: str) -> str:
        import base

        try:
            with open(image_path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            log.warning("Cannot read query image %s: %s", image_path, exc)
            return ""
        return await asyncio.to_thread(base.similarity.phash_bytes, data, _HASH_SIZE)

    async def _hash_submission_image(self, submission) -> str:
        import base

        url = getattr(submission, "url", "") or ""
        try:
            async with self._http.get(url) as resp:
                if resp.status != 200:
                    return ""
                ctype = resp.headers.get("Content-Type", "")
                if "image" not in ctype:
                    return ""
                data = await resp.read()
        except Exception as exc:
            log.debug("Download failed for %s: %s", url, exc)
            return ""
        return await asyncio.to_thread(base.similarity.phash_bytes, data, _HASH_SIZE)

    def _to_result(self, submission, distance: int) -> ReverseSearchResult:
        score = max(0.0, 1.0 - distance / _MAX_BITS)
        resolution = "Unknown"
        try:
            source = (submission.preview or {}).get("images", [{}])[0].get("source", {})
            if source.get("width") and source.get("height"):
                resolution = f"{source['width']}x{source['height']}"
        except (AttributeError, TypeError, KeyError, IndexError):
            pass
        permalink = getattr(submission, "permalink", "")
        page_url = f"https://reddit.com{permalink}" if permalink else getattr(
            submission, "url", "")
        return ReverseSearchResult(
            url=page_url,
            engine=ENGINE_SUBREDDIT_SWEEP,
            score=score,
            resolution=resolution,
            title=getattr(submission, "title", None),
        )

    def _emit_status(self, msg: str) -> None:
        if self._status_callback:
            self._status_callback(msg)
