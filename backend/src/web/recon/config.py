"""Configuration for the Entity Recon tab."""

import os
from dataclasses import dataclass, field
from typing import List

RECON_HOME = os.path.join(os.path.expanduser("~"), ".image-toolkit", "recon")
DEFAULT_CACHE_PATH = os.path.join(RECON_HOME, "provenance_cache.db")

# Embedding modes for identity resolution
EMBED_FACE = "face"     # ArcFace / InsightFace 512d — humans
EMBED_CLIP = "clip"     # CLIP — non-human / fictional characters

REVERSE_ENGINES = ["google_lens", "yandex", "bing", "saucenao"]

# Discovery scope for identity resolution
SCOPE_LOCAL = "local"   # local identity index only (fully offline)
SCOPE_WEB = "web"       # reverse-image web discovery only (skip local index)
SCOPE_BOTH = "both"     # local first, fall back to web on no local match


@dataclass
class ReconConfig:
    # --- local identity engine -------------------------------------------
    dataset_root: str = ""
    embed_mode: str = EMBED_FACE          # EMBED_FACE | EMBED_CLIP
    recursive: bool = True
    # cosine similarity a local match must clear to count as an identity
    local_match_threshold: float = 0.55
    hnsw_ef_search: int = 64
    top_k: int = 5

    # --- privacy / web ----------------------------------------------------
    # Discovery scope: SCOPE_LOCAL | SCOPE_WEB | SCOPE_BOTH.
    #   local → 100% offline (local index only)
    #   web   → reverse-image web discovery only (local index skipped)
    #   both  → local first, web fallback on no local match
    search_scope: str = SCOPE_LOCAL
    # Strict Privacy Mode: when True, ALL external dispatchers are disabled and
    # the tool runs 100% offline. Kept as the network gate the dispatcher reads;
    # it is derived from ``search_scope`` (True only for SCOPE_LOCAL).
    privacy_mode: bool = True
    reverse_engines: List[str] = field(default_factory=lambda: list(REVERSE_ENGINES))

    # --- rate limiting / caching -----------------------------------------
    cache_path: str = DEFAULT_CACHE_PATH
    # minimum seconds between requests to the same engine (anti-ban)
    min_request_interval: float = 3.0
    request_timeout: float = 15.0
    max_urls_scraped: int = 20

    # --- NLP consensus ----------------------------------------------------
    ner_model: str = "gliner"             # "gliner" | "spacy" | "heuristic"
    # a name must appear across at least this many distinct domains to win
    consensus_min_domains: int = 2

    def to_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ReconConfig":
        data = dict(data or {})
        # Legacy configs stored only ``privacy_mode``; derive the scope from it
        # when ``search_scope`` is absent so web discovery isn't silently lost.
        if "search_scope" not in data and "privacy_mode" in data:
            data["search_scope"] = SCOPE_LOCAL if data["privacy_mode"] else SCOPE_BOTH
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})
