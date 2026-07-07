"""Provenance trail data model + JSON/CSV export for OSINT record-keeping."""

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class ProvenanceEntry:
    kind: str            # "local" | "web"
    label: str           # identity name / dataset label
    source: str          # absolute file path (local) or URL (web)
    domain: str = ""     # web only
    score: float = 0.0   # similarity or consensus confidence
    method: str = ""     # e.g. "ArcFace -> Local DB", "SauceNao -> Web Consensus"

    def to_dict(self) -> dict:
        return {
            "kind": self.kind, "label": self.label, "source": self.source,
            "domain": self.domain, "score": round(self.score, 4), "method": self.method,
        }


@dataclass
class ProvenanceReport:
    query_hash: str = ""
    predicted_name: str = ""
    confidence: float = 0.0
    method: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    entries: List[ProvenanceEntry] = field(default_factory=list)

    def add(self, entry: ProvenanceEntry):
        self.entries.append(entry)

    def to_dict(self) -> dict:
        return {
            "query_hash": self.query_hash,
            "predicted_name": self.predicted_name,
            "confidence": round(self.confidence, 4),
            "method": self.method,
            "created_at": self.created_at,
            "entries": [e.to_dict() for e in self.entries],
        }


def export_provenance(report: ProvenanceReport, path: str, fmt: Optional[str] = None) -> str:
    """Write the report to *path* as JSON or CSV. Format inferred from the
    extension when *fmt* is omitted. Returns the written path."""
    fmt = (fmt or ("csv" if path.lower().endswith(".csv") else "json")).lower()
    if fmt == "csv":
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["kind", "label", "source", "domain", "score", "method"])
            writer.writerow(["#name", report.predicted_name, "", "",
                             round(report.confidence, 4), report.method])
            for e in report.entries:
                d = e.to_dict()
                writer.writerow([d["kind"], d["label"], d["source"], d["domain"],
                                 d["score"], d["method"]])
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
    return path
