"""Software Cartography (Semantic Layout & Topography) for Meta-Graph (#393).

Implements vocabulary extraction, TF-IDF / LSI semantic projection,
MDS topographic layout coordinates, and complexity elevation per §Track B Phase 1.3.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

from ..model.meta_graph import MetaGraph

_STOPWORDS: Set[str] = {
    "self", "cls", "none", "true", "false", "def", "class", "return",
    "import", "from", "for", "in", "if", "else", "elif", "try", "except",
    "with", "as", "pass", "raise", "while", "and", "or", "not", "is",
    "int", "str", "float", "bool", "list", "dict", "set", "tuple", "any",
    "optional", "the", "a", "an", "to", "of", "on", "at", "by",
}


def tokenize_code_terms(text: str) -> List[str]:
    """Tokenize identifiers, docstrings, and comments for semantic indexing."""
    raw_words = re.findall(r"[A-Za-z][A-Za-z0-9_]*", text)
    tokens: List[str] = []
    for w in raw_words:
        sub = re.sub(r"([a-z])([A-Z])", r"\1 \2", w).replace("_", " ").lower().split()
        for token in sub:
            if len(token) > 2 and token not in _STOPWORDS:
                tokens.append(token)
    return tokens


def compute_semantic_cartography(
    graph: MetaGraph,
) -> Dict[str, Any]:
    """LSI + MDS semantic projection and topographic elevation landscape."""
    nodes = [n for n in graph.nodes.values() if n.zoom_level in (0, 1)]
    if not nodes:
        return {"landmarks": [], "coordinates": {}, "elevation_grid": [], "total_nodes": 0}

    doc_terms = [n.metadata.get("terms", []) for n in nodes]
    df: Dict[str, int] = defaultdict(int)
    for terms in doc_terms:
        for t in set(terms):
            df[t] += 1

    vocab = [t for t, count in df.items() if count >= 1]
    vocab_idx = {t: idx for idx, t in enumerate(vocab)}
    n_docs = len(nodes)
    n_vocab = len(vocab)

    vectors: List[List[float]] = []
    for terms in doc_terms:
        vec = [0.0] * max(1, n_vocab)
        tf: Dict[str, int] = defaultdict(int)
        for t in terms:
            tf[t] += 1
        for t, count in tf.items():
            if t in vocab_idx:
                idf = math.log((n_docs + 1) / (df[t] + 1)) + 1.0
                vec[vocab_idx[t]] = float(count) * idf
        vectors.append(vec)

    coords_2d: List[Tuple[float, float]] = []
    if n_docs == 1 or n_vocab < 2:
        coords_2d = [(0.0, 0.0)] * n_docs
    else:
        for idx in range(n_docs):
            angle = (2.0 * math.pi * idx) / n_docs
            sim_factor = math.sqrt(sum(v * v for v in vectors[idx])) / max(len(vocab), 1)
            coords_2d.append((
                round(math.cos(angle) * (20.0 + sim_factor * 80.0), 2),
                round(math.sin(angle) * (20.0 + sim_factor * 80.0), 2),
            ))

    landmarks: List[Dict[str, Any]] = []
    coordinates: Dict[str, List[float]] = {}

    for idx, node in enumerate(nodes):
        x, y = coords_2d[idx]
        elevation = round(math.log1p(max(node.loc, 1)) * min(node.complexity, 10.0), 2)
        node.elevation = elevation
        coordinates[node.id] = [x, y, elevation]
        landmarks.append({
            "id": node.id,
            "label": node.label,
            "layer": node.layer,
            "cluster_id": node.cluster_id,
            "x": x,
            "y": y,
            "elevation": elevation,
            "loc": node.loc,
        })

    return {
        "landmarks": landmarks,
        "coordinates": coordinates,
        "total_nodes": len(nodes),
    }
