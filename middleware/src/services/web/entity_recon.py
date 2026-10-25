"""Entity reconnaissance projection service (B-06 / #911).

Qt-free surface over ``ReconEngine``: the config snapshot mirrors
``ReconConfig``, and one resolve run normalizes ``IdentityResolution``
with its provenance report into the contract payload. The engine (the
dataset index, and the web dispatcher behind the explicit scope) is
injected; with none attached every result stays ``available: false``.
Web discovery runs only at the user's explicit request; tests inject
fakes and stay offline (RESOURCE RULE: no live provider operations).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

_SCOPES = {"local", "web", "both"}
_EMBED_MODES = {"face", "clip"}


def describe_result(engine: Any | None) -> dict[str, Any]:
    """Bridge payload for ``entity_recon.describe``."""
    from middleware.src.web.recon.config import ReconConfig

    config = engine.config if engine is not None else ReconConfig()
    return {
        "available": engine is not None,
        "config": _config_snapshot(config),
    }


def resolve_result(
    engine: Any | None,
    cutout_rgb: Any,
    cutout_png: bytes,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Run one resolution through the engine and normalize the payload.

    The caller (sidecar handler) loads the image; a missing file is a
    failed resolve, not a bridge error.
    """
    if engine is None:
        return _unavailable()
    if cutout_rgb is None:
        return _failed("the cutout image could not be read")

    config = _effective_config(engine.config, params)
    engine.config = config
    # DatasetIndexer.query reads its own config.top_k. The replacement
    # config has to land there too, or the search keeps the original limit.
    _sync_indexer_config(engine, config)
    try:
        resolution = engine.resolve(cutout_rgb, cutout_png)
    except Exception as exc:  # an indexer/embedding failure is a failed resolve
        return _failed(f"{type(exc).__name__}: {exc}")
    finally:
        engine.config = config
        _sync_indexer_config(engine, config)

    report = resolution.report.to_dict() if resolution.report is not None else {}
    return {
        "available": True,
        "found": bool(resolution.found),
        "name": resolution.name,
        "confidence": float(resolution.confidence),
        "method": resolution.method,
        "origin": resolution.origin or "none",
        "local_matches": [
            {
                "label": str(match.get("label", "")),
                "path": str(match.get("path", "")),
                "score": float(match.get("score", 0.0)),
            }
            for match in resolution.local_matches
        ],
        "web_domains": [
            {
                "domain": str(domain.get("domain", "")),
                "count": int(domain.get("count", 0)),
                "urls": [str(url) for url in domain.get("urls", [])],
            }
            for domain in resolution.web_domains
        ],
        "report": {
            "query_hash": str(report.get("query_hash", "")),
            "predicted_name": str(report.get("predicted_name", "")),
            "confidence": float(report.get("confidence", 0.0)),
            "method": str(report.get("method", "")),
            "created_at": str(report.get("created_at", "")),
            "entries": [
                {
                    "kind": str(entry.get("kind", "")),
                    "label": str(entry.get("label", "")),
                    "source": str(entry.get("source", "")),
                    "domain": str(entry.get("domain", "")),
                    "score": float(entry.get("score", 0.0)),
                    "method": str(entry.get("method", "")),
                }
                for entry in report.get("entries", [])
            ],
        },
        "error": None,
    }


def _effective_config(config: Any, params: Mapping[str, Any]) -> Any:
    """Apply the caller's validated overrides to the engine config."""
    overrides: dict[str, Any] = {}
    scope = params.get("search_scope")
    if scope in _SCOPES:
        overrides["search_scope"] = scope
        # privacy_mode is derived from the scope (True only for local).
        overrides["privacy_mode"] = scope == "local"
    threshold = params.get("local_match_threshold")
    if isinstance(threshold, (int, float)) and 0 <= threshold <= 1:
        overrides["local_match_threshold"] = float(threshold)
    top_k = params.get("top_k")
    if isinstance(top_k, int) and top_k >= 1:
        overrides["top_k"] = top_k
    if params.get("embed_mode") in _EMBED_MODES:
        overrides["embed_mode"] = params["embed_mode"]
    if not overrides:
        return config
    return replace(config, **overrides)


def _sync_indexer_config(engine: Any, config: Any) -> None:
    indexer = getattr(engine, "indexer", None)
    if indexer is not None and hasattr(indexer, "config"):
        indexer.config = config


def _config_snapshot(config: Any) -> dict[str, Any]:
    return {
        "search_scope": config.search_scope,
        "privacy_mode": bool(config.privacy_mode),
        "local_match_threshold": float(config.local_match_threshold),
        "top_k": int(config.top_k),
        "embed_mode": config.embed_mode,
        "reverse_engines": [str(engine) for engine in config.reverse_engines],
    }


def _unavailable() -> dict[str, Any]:
    return {
        "available": False,
        "found": False,
        "name": "",
        "confidence": 0.0,
        "method": "",
        "origin": "none",
        "local_matches": [],
        "web_domains": [],
        "report": {
            "query_hash": "",
            "predicted_name": "",
            "confidence": 0.0,
            "method": "",
            "created_at": "",
            "entries": [],
        },
        "error": None,
    }


def _failed(reason: str) -> dict[str, Any]:
    payload = _unavailable()
    payload["available"] = True
    payload["error"] = reason
    return payload


__all__ = [
    "describe_result",
    "resolve_result",
]
