"""Provenance cache, rate limiter and privacy-gated dispatch tests."""

import time

from backend.src.web.recon.config import ReconConfig
from backend.src.web.recon.dispatcher import (
    ProvenanceCache,
    RateLimiter,
    ReverseSearchDispatcher,
    WebHit,
)


class TestRateLimiter:
    def test_allow_then_block(self):
        rl = RateLimiter(min_interval=10.0)
        assert rl.allow("google") is True
        assert rl.allow("google") is False       # too soon
        assert rl.allow("bing") is True           # different key

    def test_allow_after_interval(self):
        rl = RateLimiter(min_interval=0.05)
        assert rl.allow("k") is True
        time.sleep(0.06)
        assert rl.allow("k") is True


class TestProvenanceCache:
    def test_roundtrip(self):
        cache = ProvenanceCache(":memory:")
        hits = [WebHit(url="https://reddit.com/x", title="T", snippet="S", engine="yandex")]
        cache.put("hash1", "yandex", hits)
        got = cache.get("hash1", "yandex")
        assert got and got[0].url == "https://reddit.com/x"
        assert got[0].domain == "reddit.com"

    def test_miss_returns_none(self):
        assert ProvenanceCache(":memory:").get("nope", "bing") is None


class TestDispatch:
    def test_privacy_mode_never_calls_network(self, monkeypatch):
        cfg = ReconConfig(privacy_mode=True, cache_path=":memory:")
        disp = ReverseSearchDispatcher(cfg)

        def _boom(*a, **k):
            raise AssertionError("network hit in privacy mode")

        monkeypatch.setattr(disp, "_query_engine", _boom)
        result = disp.dispatch(b"cutout-bytes")
        assert result.skipped_privacy is True
        assert result.hits == []

    def test_privacy_mode_serves_cache(self):
        cfg = ReconConfig(privacy_mode=True, cache_path=":memory:",
                          reverse_engines=["yandex"])
        disp = ReverseSearchDispatcher(cfg)
        h = disp.cutout_hash(b"cutout-bytes")
        disp.cache.put(h, "yandex", [WebHit(url="https://x.com/a", engine="yandex")])
        result = disp.dispatch(b"cutout-bytes")
        assert result.skipped_privacy is True
        assert len(result.hits) == 1
        assert result.from_cache.get("yandex") is True

    def test_web_mode_caches_results(self, monkeypatch):
        cfg = ReconConfig(privacy_mode=False, cache_path=":memory:",
                          reverse_engines=["bing"], min_request_interval=0.0)
        disp = ReverseSearchDispatcher(cfg)
        calls = {"n": 0}

        def _fake(engine, png):
            calls["n"] += 1
            return [WebHit(url="https://bing.com/r", engine=engine)]

        monkeypatch.setattr(disp, "_query_engine", _fake)
        r1 = disp.dispatch(b"same-cutout")
        r2 = disp.dispatch(b"same-cutout")
        assert calls["n"] == 1                      # second served from cache
        assert r2.from_cache.get("bing") is True
        assert len(r1.hits) == 1 and len(r2.hits) == 1
