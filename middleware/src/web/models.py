from dataclasses import dataclass
from typing import Optional


@dataclass
class ReverseSearchResult:
    """Normalised result returned by any reverse image search engine.

    Attributes:
        url: Web URL for online results; absolute local path for CBIR results.
        engine: Identifier of the engine that produced this result
            ("google", "tineye", "local_cbir").
        score: Similarity / confidence score in [0.0, 1.0].  Higher is better.
            Google results receive 1.0 (no ranking signal from scraping).
        resolution: Human-readable dimension string, e.g. ``"1920x1080"``,
            or ``"Unknown"`` when unavailable.
        title: Optional page title or filename label.
    """

    url: str
    engine: str
    score: float = 1.0
    resolution: str = "Unknown"
    title: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialise to the legacy ``Dict[str, str]`` format expected by the GUI."""
        return {
            "url": self.url,
            "resolution": self.resolution,
            "score": f"{self.score:.4f}",
            "engine": self.engine,
            "title": self.title or "",
        }
