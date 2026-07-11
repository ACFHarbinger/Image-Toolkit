"""Entity Recon and Provenance — localized OSINT / identity-resolution backend.

Cross-language split:
    C++  (base.recon)   HNSW identity index + alpha-cutout hashing
    Python (this pkg)   SAM 2 segmentation, face/CLIP embeddings, dataset
                        indexing daemon, reverse-search dispatch, NER consensus
    Rust                (spec called for Rust; the base module completed its
                         Rust→C++ migration, so the native engine is C++)

Everything degrades gracefully: heavy models (SAM 2, InsightFace, gliner/spaCy)
are lazy-loaded and fall back when unavailable so the tab stays usable offline.
"""

from .config import ReconConfig as ReconConfig
from .consensus import ConsensusResult as ConsensusResult
from .consensus import consensus_names as consensus_names
from .dispatcher import ProvenanceCache as ProvenanceCache
from .dispatcher import RateLimiter as RateLimiter
from .dispatcher import ReverseSearchDispatcher as ReverseSearchDispatcher
from .engine import IdentityResolution as IdentityResolution
from .engine import ReconEngine as ReconEngine
from .indexer import DatasetIndexer as DatasetIndexer
from .provenance import ProvenanceReport as ProvenanceReport
from .provenance import export_provenance as export_provenance

__all__ = [
    "ConsensusResult",
    "DatasetIndexer",
    "IdentityResolution",
    "ProvenanceCache",
    "ProvenanceReport",
    "RateLimiter",
    "ReconConfig",
    "ReconEngine",
    "ReverseSearchDispatcher",
    "consensus_names",
    "export_provenance",
]
