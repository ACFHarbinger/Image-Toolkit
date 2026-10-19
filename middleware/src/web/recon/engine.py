"""Identity-resolution orchestration.

resolve(cutout) →
    1. embed the alpha cutout,
    2. query the local HNSW identity index,
    3. if the best local match clears the threshold → Local DB result,
    4. otherwise (and only if privacy mode is off) dispatch a reverse image
       search, scrape + NER the results and compute a web consensus identity.

Produces an :class:`IdentityResolution` plus a :class:`ProvenanceReport`.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .config import EMBED_FACE, SCOPE_BOTH, SCOPE_LOCAL, SCOPE_WEB, ReconConfig
from .consensus import consensus_names
from .dispatcher import ReverseSearchDispatcher
from .embedder import embed
from .indexer import DatasetIndexer
from .provenance import ProvenanceEntry, ProvenanceReport

logger = logging.getLogger(__name__)


@dataclass
class IdentityResolution:
    name: str = ""
    confidence: float = 0.0
    method: str = ""          # e.g. "ArcFace -> Local DB"
    origin: str = ""          # "local" | "web" | "none"
    report: Optional[ProvenanceReport] = None
    local_matches: List[dict] = field(default_factory=list)   # {label,path,score}
    web_domains: List[dict] = field(default_factory=list)     # {domain,count,urls}

    @property
    def found(self) -> bool:
        return bool(self.name)


class ReconEngine:
    def __init__(
        self,
        config: ReconConfig,
        indexer: Optional[DatasetIndexer] = None,
        dispatcher: Optional[ReverseSearchDispatcher] = None,
    ):
        self.config = config
        self.indexer = indexer or DatasetIndexer(config)
        self.dispatcher = dispatcher or ReverseSearchDispatcher(config)

    def _method_label(self) -> str:
        return "ArcFace" if self.config.embed_mode == EMBED_FACE else "CLIP"

    def resolve(self, cutout_rgb: np.ndarray, cutout_png: bytes) -> IdentityResolution:
        report = ProvenanceReport(method="", predicted_name="")
        res = IdentityResolution(report=report)

        # Resolve the effective scope. ``search_scope`` is authoritative; fall
        # back to the legacy ``privacy_mode`` flag for configs that predate it.
        scope = getattr(self.config, "search_scope", None)
        if scope not in (SCOPE_LOCAL, SCOPE_WEB, SCOPE_BOTH):
            scope = SCOPE_LOCAL if self.config.privacy_mode else SCOPE_BOTH
        do_local = scope in (SCOPE_LOCAL, SCOPE_BOTH)
        do_web = scope in (SCOPE_WEB, SCOPE_BOTH)

        # --- 1. local identity index -------------------------------------
        if do_local:
            embedding = embed(cutout_rgb, self.config.embed_mode)
            if embedding is None:
                res.method = "no subject embedding"
                res.origin = "none"
                if not do_web:
                    return res
            else:
                matches = self.indexer.query(embedding)
                res.local_matches = [
                    {"label": label, "path": path, "score": float(score)}
                    for label, path, score in matches
                ]
                if matches and matches[0][2] >= self.config.local_match_threshold:
                    label, path, score = matches[0]
                    res.name = label.replace("_", " ")
                    res.confidence = float(score)
                    res.method = f"{self._method_label()} -> Local DB"
                    res.origin = "local"
                    report.predicted_name = res.name
                    report.confidence = res.confidence
                    report.method = res.method
                    for m_label, m_path, m_score in matches:
                        report.add(ProvenanceEntry(
                            kind="local", label=m_label.replace("_", " "), source=m_path,
                            score=float(m_score), method=res.method,
                        ))
                    return res

        # --- 2. web discovery --------------------------------------------
        if not do_web:
            res.method = "Local DB (no match) · web disabled (local-only scope)"
            res.origin = "none"
            report.query_hash = self.dispatcher.cutout_hash(cutout_png)
            report.method = res.method
            return res

        dispatch = self.dispatcher.dispatch(cutout_png)
        report.query_hash = dispatch.cutout_hash

        # group hits by domain for the provenance tree
        by_domain: dict = {}
        documents = []
        for hit in dispatch.hits:
            by_domain.setdefault(hit.domain, []).append(hit)
            documents.append((hit.domain, f"{hit.title}\n{hit.snippet}"))
            report.add(ProvenanceEntry(
                kind="web", label="", source=hit.url, domain=hit.domain,
                method=f"{hit.engine} -> Web",
            ))
        res.web_domains = [
            {"domain": d, "count": len(hits), "urls": [h.url for h in hits]}
            for d, hits in sorted(by_domain.items(), key=lambda kv: -len(kv[1]))
        ]

        consensus = consensus_names(
            documents, min_domains=self.config.consensus_min_domains,
            model=self.config.ner_model,
        )
        if consensus.found:
            res.name = consensus.name
            res.confidence = consensus.confidence
            res.method = "Web Consensus"
            res.origin = "web"
            report.predicted_name = res.name
            report.confidence = res.confidence
            report.method = res.method
            for entry in report.entries:
                if entry.kind == "web" and entry.domain in consensus.domains:
                    entry.label = consensus.name
        else:
            res.method = "Web search (no consensus)"
            res.origin = "none"
        return res

    # --- batch dataset builder -------------------------------------------

    def suggest_batch(self, image_paths: List[str]) -> List[dict]:
        """For a dropped batch, resolve each image against the local index and
        propose a folder move ``FirstName_LastName/``. Returns per-image
        suggestions for the QML approve-all list."""
        import cv2

        suggestions = []
        for path in image_paths:
            img = cv2.imread(path)
            if img is None:
                continue
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            embedding = embed(rgb, self.config.embed_mode)
            if embedding is None:
                continue
            matches = self.indexer.query(embedding)
            if matches and matches[0][2] >= self.config.local_match_threshold:
                label, _mpath, score = matches[0]
                suggestions.append({
                    "path": path,
                    "suggested_label": label,
                    "score": float(score),
                    "target_dir": os.path.join(os.path.dirname(path), label),
                })
            else:
                suggestions.append({
                    "path": path, "suggested_label": "", "score": 0.0,
                    "target_dir": "",
                })
        return suggestions
