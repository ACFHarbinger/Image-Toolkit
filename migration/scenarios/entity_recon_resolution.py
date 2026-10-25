"""Entity recon differential: the Qt worker's payload vs the service
projection (B-06 / #911, #883 harness).

The legacy side projects an ``IdentityResolution`` exactly as the Qt
worker's ``ResolveWorker`` carried it (resolution fields plus
``ProvenanceReport.to_dict()``); the service side projects
``resolve_result`` over the same fake engine. No dataset index is built
and no web dispatch runs — the fake engine answers offline.
"""

from __future__ import annotations

from middleware.src.services.web.entity_recon import resolve_result


class _FakeReport:
    def to_dict(self) -> dict[str, object]:
        return {
            "query_hash": "abc123",
            "predicted_name": "rin tohsaka",
            "confidence": 0.91,
            "method": "ArcFace -> Local DB",
            "created_at": "2026-10-25T00:00:00+00:00",
            "entries": [
                {
                    "kind": "local",
                    "label": "rin tohsaka",
                    "source": "/dataset/rin/001.png",
                    "score": 0.91,
                    "method": "ArcFace -> Local DB",
                }
            ],
        }


class _FakeResolution:
    name = "rin tohsaka"
    confidence = 0.91
    method = "ArcFace -> Local DB"
    origin = "local"
    report = _FakeReport()
    local_matches = [{"label": "rin_tohsaka", "path": "/dataset/rin/001.png", "score": 0.91}]
    web_domains: list[dict[str, object]] = []

    @property
    def found(self) -> bool:
        return bool(self.name)


class _FakeEngine:
    def __init__(self) -> None:
        from middleware.src.web.recon.config import ReconConfig

        self.config = ReconConfig()

    def resolve(self, cutout_rgb, cutout_png):
        return _FakeResolution()


def pair(tmp: object) -> tuple[dict[str, object], dict[str, object]]:
    return _legacy(), _service()


def _legacy() -> dict[str, object]:
    resolution = _FakeResolution()
    report = resolution.report.to_dict()
    # The Qt tree only carries a domain for web entries; the service
    # normalizes it into every entry, so the legacy projection does too.
    entries = [
        {**entry, "domain": entry.get("domain", "")}
        for entry in report["entries"]
    ]
    return {
        "found": resolution.found,
        "name": resolution.name,
        "confidence": resolution.confidence,
        "method": resolution.method,
        "origin": resolution.origin,
        "report": {**report, "entries": entries},
    }


def _service() -> dict[str, object]:
    result = resolve_result(_FakeEngine(), "rgb", b"png", {"image_path": "/cutout.png"})
    return {
        "found": result["found"],
        "name": result["name"],
        "confidence": result["confidence"],
        "method": result["method"],
        "origin": result["origin"],
        "report": result["report"],
    }
