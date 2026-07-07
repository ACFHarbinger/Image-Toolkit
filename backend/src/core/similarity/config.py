"""Hyperparameter configuration for the Similarity Finder.

Every field here is surfaced in the GUI settings panel; keep defaults sane for
a cold run on a typical photo library.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional

DEFAULT_CACHE_PATH = os.path.join(
    os.path.expanduser("~"), ".image-toolkit", "similarity_cache.db"
)

# Detection tiers (bitmask-style string identifiers)
TIER_EXACT = "exact"            # Tier 1 — xxHash64 bit-for-bit duplicates
TIER_PERCEPTUAL = "perceptual"  # Tier 2 — pHash/dHash/wHash consensus
TIER_STRUCTURAL = "structural"  # Tier 3 — SSIM + ORB/SIFT geometric verify
TIER_SEMANTIC = "semantic"      # Tier 4 — CLIP/MobileCLIP embeddings + HNSW

ALL_TIERS = [TIER_EXACT, TIER_PERCEPTUAL, TIER_STRUCTURAL, TIER_SEMANTIC]

EMBED_MODELS = ["mobileclip", "openclip", "resnet18"]


@dataclass
class SimilarityConfig:
    """Full scan configuration. All algorithm hyperparameters live here."""

    # --- scan scope -------------------------------------------------------
    target_dir: str = ""
    # Directional mode: pairs entirely inside the reference directory are
    # ignored; only reference<->target and target<->target pairs survive.
    reference_dir: Optional[str] = None
    extensions: List[str] = field(
        default_factory=lambda: [".jpg", ".jpeg", ".png", ".webp", ".bmp"]
    )
    recursive: bool = True
    tiers: List[str] = field(default_factory=lambda: [TIER_EXACT, TIER_PERCEPTUAL])

    # --- persistence ------------------------------------------------------
    cache_path: str = DEFAULT_CACHE_PATH

    # --- Tier 2: consensus hashing ---------------------------------------
    hash_size: int = 16            # 8 | 16 | 32
    hamming_threshold: int = 10    # scaled internally with hash_size²/64

    # --- Tier 3: structural / geometric ----------------------------------
    feature_method: str = "orb"    # "orb" | "sift"
    max_features: int = 1000
    lowe_ratio: float = 0.75
    ransac_threshold: float = 5.0
    min_inliers: int = 25
    ssim_threshold: float = 0.90
    ssim_resize: int = 256
    # cap on structural verifications per scan (each costs ~50-300 ms)
    max_structural_pairs: int = 2000

    # --- Tier 4: semantic embeddings --------------------------------------
    embed_model: str = "mobileclip"      # one of EMBED_MODELS
    similarity_threshold: float = 0.90   # cosine similarity for a semantic edge
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    hnsw_ef_search: int = 64
    hnsw_k: int = 16

    # --- clustering --------------------------------------------------------
    # Edges below this confidence are dropped before union-find grouping.
    # The QML slider re-runs only this stage (no rescan).
    confidence_threshold: float = 0.75

    def scaled_hamming_threshold(self) -> int:
        """Hamming thresholds are calibrated for 64-bit hashes; scale to the
        actual bit count so an 8 at hash_size=8 means the same visual laxity
        as at hash_size=32."""
        total_bits = self.hash_size * self.hash_size
        return max(1, round(self.hamming_threshold * total_bits / 64.0))

    def to_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SimilarityConfig":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


@dataclass
class TriageRules:
    """Auto-selection rules deciding which file in a cluster to KEEP.

    Rules are applied as a weighted score; the highest-scoring file is the
    keeper, every other file in the cluster is marked for action.
    """

    prefer_highest_resolution: bool = True
    prefer_largest_file: bool = True
    prefer_lossless_format: bool = True
    prefer_exif_metadata: bool = True
    # Substrings ranked from most to least preferred, matched against the
    # file's directory (e.g. ["Archive", "Pictures", "Downloads"]).
    path_priority: List[str] = field(default_factory=lambda: ["archive", "pictures"])
    path_deprioritize: List[str] = field(
        default_factory=lambda: ["download", "cache", "tmp", "temp"]
    )

    # Relative rule weights
    weight_resolution: float = 3.0
    weight_file_size: float = 1.0
    weight_format: float = 2.0
    weight_exif: float = 1.5
    weight_path: float = 2.5

    def to_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TriageRules":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (data or {}).items() if k in known})
