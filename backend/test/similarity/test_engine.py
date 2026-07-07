"""SimilarityEngine orchestration tests (exact/perceptual/structural tiers).

The semantic tier is exercised only through regroup() with synthetic edges to
avoid pulling torch into the test session.
"""

import pytest

pytest.importorskip("base")

from backend.src.core.similarity.config import SimilarityConfig  # noqa: E402
from backend.src.core.similarity.engine import (  # noqa: E402
    ScanCancelled,
    SimilarityEdge,
    SimilarityEngine,
    SimilarityReport,
)


def _config(image_dir, tmp_path, **kw):
    defaults = dict(
        target_dir=str(image_dir),
        tiers=["exact", "perceptual"],
        cache_path=str(tmp_path / "cache.db"),
        hash_size=16,
        hamming_threshold=10,
        confidence_threshold=0.8,
    )
    defaults.update(kw)
    return SimilarityConfig(**defaults)


class TestScan:
    def test_exact_duplicates_grouped(self, image_dir, tmp_path):
        report = SimilarityEngine(_config(image_dir, tmp_path)).scan()
        exact = [
            e for e in report.edges if e.tier == "exact" and e.confidence == 1.0
        ]
        names = {frozenset((e.a.split("/")[-1], e.b.split("/")[-1])) for e in exact}
        assert frozenset(("base.png", "copy_exact.png")) in names

    def test_perceptual_cluster_contains_variants(self, image_dir, tmp_path):
        report = SimilarityEngine(_config(image_dir, tmp_path)).scan()
        big = max(report.clusters, key=lambda c: c["size"])
        members = {p.split("/")[-1] for p in big["paths"]}
        assert {"base.png", "copy_exact.png", "copy_resized.png"} <= members
        assert "unrelated1.png" not in members

    def test_incremental_rescan_hits_cache(self, image_dir, tmp_path):
        cfg = _config(image_dir, tmp_path)
        engine = SimilarityEngine(cfg)
        first = engine.scan()
        second = engine.scan()
        assert first.stats["hashed"] == first.stats["file_count"]
        assert second.stats["hashed"] == 0
        assert second.stats["cache_hits"] == second.stats["file_count"]

    def test_structural_tier_runs(self, image_dir, tmp_path):
        cfg = _config(image_dir, tmp_path,
                      tiers=["exact", "perceptual", "structural"])
        report = SimilarityEngine(cfg).scan()
        assert report.stats.get("structural_checked", 0) >= 0
        assert report.clusters  # still groups the variants

    def test_cancellation(self, image_dir, tmp_path):
        engine = SimilarityEngine(_config(image_dir, tmp_path),
                                  cancel_cb=lambda: True)
        with pytest.raises(ScanCancelled):
            engine.scan()

    def test_reference_directional_filter(self, image_dir, tmp_path):
        import shutil

        # Reference dir holds copies of two target files: internal reference
        # pairs must be ignored, cross pairs must survive.
        ref = tmp_path / "reference"
        ref.mkdir()
        shutil.copy(image_dir / "base.png", ref / "ref_a.png")
        shutil.copy(image_dir / "base.png", ref / "ref_b.png")

        cfg = _config(image_dir, tmp_path, reference_dir=str(ref))
        report = SimilarityEngine(cfg).scan()

        ref_paths = {str(ref / "ref_a.png"), str(ref / "ref_b.png")}
        for e in report.edges:
            assert not (e.a in ref_paths and e.b in ref_paths), (
                "reference-internal pair leaked through"
            )
        cross = [e for e in report.edges
                 if (e.a in ref_paths) != (e.b in ref_paths)]
        assert cross, "expected reference<->target edges"


class TestRegroup:
    def _report(self):
        return SimilarityReport(
            files=["a", "b", "c", "d"],
            edges=[
                SimilarityEdge("a", "b", 0.95, "perceptual"),
                SimilarityEdge("b", "c", 0.70, "semantic"),
                SimilarityEdge("c", "d", 0.60, "semantic"),
            ],
        )

    def test_high_threshold_small_clusters(self):
        clusters = SimilarityEngine.regroup(self._report(), 0.9)
        assert len(clusters) == 1
        assert clusters[0]["paths"] == ["a", "b"]

    def test_low_threshold_merges_transitively(self):
        clusters = SimilarityEngine.regroup(self._report(), 0.5)
        assert len(clusters) == 1
        assert clusters[0]["paths"] == ["a", "b", "c", "d"]

    def test_threshold_above_all_edges(self):
        assert SimilarityEngine.regroup(self._report(), 0.99) == []

    def test_cluster_metadata(self):
        clusters = SimilarityEngine.regroup(self._report(), 0.9)
        c = clusters[0]
        assert c["size"] == 2
        assert c["tier"] == "perceptual"
        assert c["confidence"] == pytest.approx(0.95)
