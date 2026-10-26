"""Web service package (B-05 / #910, B-06 / #911)."""

from .entity_recon import describe_result as entity_recon_describe_result
from .entity_recon import resolve_result as entity_recon_resolve_result

__all__ = [
    "entity_recon_describe_result",
    "entity_recon_resolve_result",
from .reverse_search import ENGINE_LABELS, engines_result, search_result

__all__ = [
    "ENGINE_LABELS",
    "engines_result",
    "search_result",
]
