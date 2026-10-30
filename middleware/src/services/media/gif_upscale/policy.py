"""Weights-policy setting and the on-demand cache (#1127).

``gif_upscale.weights_policy`` is ``on_demand`` (default), ``prefetch_all``, or ``offline``.
Downloads are SHA-256 checked. ``offline`` never opens a network connection.
The key is an extension setting, not a frozen gui catalog key.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Callable

from middleware.src.settings.keys import SettingDefinition, register_definitions
from middleware.src.settings.scopes import SettingScope

WEIGHTS_POLICY_KEY = "gif_upscale.weights_policy"
POLICIES = ("on_demand", "prefetch_all", "offline")
_ENV = "IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY"
_CACHE_ENV = "IMAGE_TOOLKIT_GIF_UPSCALE_CACHE"

WEIGHTS_POLICY_DEFINITION = SettingDefinition(
    key=WEIGHTS_POLICY_KEY,
    scope=SettingScope.DEVICE,
    default="on_demand",
    value_type=str,
    description="How GIF upscale weights are fetched: on_demand, prefetch_all, or offline.",
    validator=lambda value: str(value).strip().lower() in POLICIES,
)

register_definitions([WEIGHTS_POLICY_DEFINITION])

Fetch = Callable[[str, Path], None]


class WeightUnavailable(Exception):
    """A weight file is missing, mismatched, or blocked by the offline policy."""


def weights_policy(service: Any | None = None) -> str:
    """The active policy. ``IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY`` wins over the setting."""
    raw = os.environ.get(_ENV)
    if raw is not None and str(raw).strip():
        return _normalize(raw)
    if service is None:
        from middleware.src.settings.service import SettingsService

        service = SettingsService()
    return _normalize(service.get(WEIGHTS_POLICY_KEY, "on_demand"))


def cache_dir() -> Path:
    override = os.environ.get(_CACHE_ENV)
    if override:
        return Path(override)
    return Path.home() / ".cache" / "image-toolkit" / "gif-upscale"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_weight(
    filename: str,
    sha256: str,
    url: str,
    policy: str,
    *,
    cache: Path | None = None,
    fetch: Fetch | None = None,
) -> Path:
    """Return a cached weight. Download only when the policy allows it."""
    policy = _normalize(policy)
    root = cache if cache is not None else cache_dir()
    destination = root / filename
    if destination.is_file():
        actual = sha256_file(destination)
        if actual == sha256.lower():
            return destination
        if policy == "offline":
            raise WeightUnavailable(
                f"Cached {filename} sha256 {actual} does not match {sha256}, and policy is offline."
            )
        destination.unlink()
    if policy == "offline":
        raise WeightUnavailable(f"Weight {filename} is not cached, and policy is offline.")
    if not url:
        raise WeightUnavailable(f"Weight {filename} has no download URL.")
    root.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    try:
        (fetch or _download)(url, temporary)
        actual = sha256_file(temporary)
        if actual != sha256.lower():
            raise WeightUnavailable(f"Downloaded {filename} sha256 {actual} does not match {sha256}.")
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def _normalize(raw: object) -> str:
    value = str(raw).strip().lower()
    if value not in POLICIES:
        raise ValueError(
            f"{WEIGHTS_POLICY_KEY} must be one of {', '.join(POLICIES)}; got {raw!r}."
        )
    return value


def _download(url: str, destination: Path) -> None:
    import urllib.request

    urllib.request.urlretrieve(url, destination)  # noqa: S310 — URL comes from the registry, not a request.
