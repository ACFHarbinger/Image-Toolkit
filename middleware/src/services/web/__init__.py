"""Web service package (B-05 / #910, B-06 / #911)."""

from .reverse_search import ENGINE_LABELS, engines_result, search_result

__all__ = [
    "ENGINE_LABELS",
    "engines_result",
    "search_result",
]
