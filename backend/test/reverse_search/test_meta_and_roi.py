"""Meta-dispatcher consensus, URL builder, C++ ROI/pHash and sweep-mapping tests."""

import asyncio

import numpy as np
import pytest

from backend.src.web.meta_search_dispatcher import MetaSearchDispatcher
from backend.src.web.models import ReverseSearchResult
from backend.src.web.search_url_builder import DomainScope, SearchOperatorBuilder


class _FakeEngine:
    def __init__(self, results):
        self._results = results

    def search(self, image_path, **kwargs):
        return self._results

    def stop(self):
        pass


class TestConsensus:
    def _dispatcher(self, overrides, engines):
        return MetaSearchDispatcher(
            enabled_engines=engines, engine_factory_overrides=overrides
        )

    def test_agreement_boosts_score(self):
        disp = self._dispatcher(
            {
                "a": lambda: _FakeEngine([ReverseSearchResult(
                    "https://reddit.com/x/", "a", 0.8, "800x600", "T")]),
                "b": lambda: _FakeEngine([ReverseSearchResult(
                    "http://reddit.com/x", "b", 0.7, "1920x1080")]),
                "c": lambda: _FakeEngine([ReverseSearchResult(
                    "https://other.com/y", "c", 0.9)]),
            },
            ["a", "b", "c"],
        )
        results = asyncio.run(disp.search_all("dummy.jpg"))
        reddit = next(c for c in results if "reddit" in c.url)
        assert set(reddit.engines) == {"a", "b"}
        assert reddit.consensus_score > reddit.best_score   # boosted
        assert reddit.resolution == "1920x1080"             # better merged

    def test_canonical_key_merges_variants(self):
        disp = self._dispatcher(
            {
                "a": lambda: _FakeEngine([ReverseSearchResult(
                    "https://Site.com/Path/", "a", 0.5)]),
                "b": lambda: _FakeEngine([ReverseSearchResult(
                    "http://site.com/Path", "b", 0.6)]),
            },
            ["a", "b"],
        )
        results = asyncio.run(disp.search_all("dummy.jpg"))
        assert len(results) == 1
        assert set(results[0].engines) == {"a", "b"}

    def test_single_engine_failure_isolated(self):
        class _BoomEngine:
            def search(self, image_path, **kwargs):
                raise RuntimeError("engine down")

            def stop(self):
                pass

        disp = self._dispatcher(
            {
                "a": lambda: _FakeEngine([ReverseSearchResult("https://ok.com/1", "a", 0.9)]),
                "b": lambda: _BoomEngine(),
            },
            ["a", "b"],
        )
        results = asyncio.run(disp.search_all("dummy.jpg"))
        assert len(results) == 1 and results[0].url == "https://ok.com/1"

    def test_ranked_descending(self):
        disp = self._dispatcher(
            {
                "a": lambda: _FakeEngine([ReverseSearchResult("https://a.com/1", "a", 0.3)]),
                "b": lambda: _FakeEngine([ReverseSearchResult("https://b.com/2", "b", 0.9)]),
            },
            ["a", "b"],
        )
        results = asyncio.run(disp.search_all("dummy.jpg"))
        assert [c.url for c in results] == ["https://b.com/2", "https://a.com/1"]


class TestUrlBuilder:
    def test_site_operator_and_terms(self):
        b = SearchOperatorBuilder(base_terms=["1girl", "blue sword"]).add_subreddit("art")
        q = b.build_query_string()
        assert "site:reddit.com/r/art" in q
        assert '"blue sword"' in q and "1girl" in q

    def test_exclusion_operator(self):
        b = SearchOperatorBuilder(scopes=[DomainScope("pinterest.com", exclude=True)])
        assert b.build_query_string() == "-site:pinterest.com"

    def test_build_url_encodes(self):
        b = SearchOperatorBuilder(base_terms=["cat"])
        url = b.build_url("https://www.google.com/search")
        assert url.startswith("https://www.google.com/search?q=")


class TestCppRoiPhash:
    def test_phash_bytes_matches_path(self, tmp_path):
        base = pytest.importorskip("base")
        import cv2

        img = np.random.default_rng(0).integers(0, 255, (128, 128, 3), dtype=np.uint8)
        p = str(tmp_path / "a.png")
        cv2.imwrite(p, img)
        with open(p, "rb") as f:
            hb = base.similarity.phash_bytes(f.read(), 16)
        rec = base.similarity.compute_hashes([p], hash_size=16)[0]
        assert hb == rec["phash"]

    def test_batch_hamming(self):
        base = pytest.importorskip("base")
        q = "ff00ff00ff00ff00"
        out = base.similarity.batch_hamming(q, [q, "0000000000000000", ""])
        # self distance 0; empty candidate skipped
        assert out[0] == (0, 0)
        assert all(idx != 2 for idx, _d in out)

    def test_crop_roi_clamps(self, tmp_path):
        base = pytest.importorskip("base")
        import cv2

        img = np.zeros((100, 200, 3), dtype=np.uint8)
        p = str(tmp_path / "a.png")
        cv2.imwrite(p, img)
        r = base.roi.crop_roi(p, 150, 50, 9999, 9999)   # over-wide
        assert r["ok"]
        assert r["width"] == 50 and r["height"] == 50   # clamped to bounds

    def test_crop_roi_bad_path(self):
        base = pytest.importorskip("base")
        r = base.roi.crop_roi("/nonexistent.png", 0, 0, 10, 10)
        assert not r["ok"] and r["error"]


class TestSweepMapping:
    def test_to_result_scoring(self):
        from backend.src.web.subreddit_phash_sweep import (
            SubredditPHashSweep,
            SubredditSweepConfig,
        )

        sweep = SubredditPHashSweep(SubredditSweepConfig(subreddit="art"))

        class _Sub:
            url = "https://i.redd.it/x.jpg"
            permalink = "/r/art/comments/1/x/"
            title = "Post"
            preview = {"images": [{"source": {"width": 1000, "height": 800}}]}

        r = sweep._to_result(_Sub(), distance=2)
        assert r.url == "https://reddit.com/r/art/comments/1/x/"
        assert r.resolution == "1000x800"
        assert abs(r.score - (1 - 2 / 64)) < 1e-6
