"""Cloud Compute setup service package (T-04 / #920)."""

from .providers import is_provider, provider_ids, providers_result

__all__ = [
    "is_provider",
    "provider_ids",
    "providers_result",
]
