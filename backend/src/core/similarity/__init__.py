"""Similarity Finder backend: tiered duplicate/similarity detection engine.

Layers:
    config       — hyperparameter dataclasses exposed to the GUI
    cache        — SQLite incremental scan cache (hashes + embeddings)
    embedder     — local CLIP/MobileCLIP/ResNet embedding models
    engine       — 4-tier orchestration on top of the C++ ``base.similarity`` core
    triage       — heuristic auto-selection rule engine
    consolidate  — hardlink/symlink space reclamation
"""

from .cache import SimilarityCache as SimilarityCache
from .config import SimilarityConfig as SimilarityConfig
from .config import TriageRules as TriageRules
from .consolidate import consolidate_cluster as consolidate_cluster
from .embedder import get_embedder as get_embedder
from .engine import SimilarityEngine as SimilarityEngine
from .engine import SimilarityReport as SimilarityReport
from .triage import auto_select as auto_select

__all__ = [
    "SimilarityCache",
    "SimilarityConfig",
    "SimilarityEngine",
    "SimilarityReport",
    "TriageRules",
    "auto_select",
    "consolidate_cluster",
    "get_embedder",
]
