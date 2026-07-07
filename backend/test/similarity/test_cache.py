"""SQLite incremental-scan cache tests."""

import os
import time

import numpy as np
import pytest

from backend.src.core.similarity.cache import SimilarityCache


@pytest.fixture
def cache(tmp_path):
    c = SimilarityCache(str(tmp_path / "cache.db"))
    yield c
    c.close()


def _touch(path, content=b"data"):
    with open(path, "wb") as f:
        f.write(content)


def _record(path):
    return {
        "path": str(path), "ok": True, "xxh64": "aa",
        "phash": "ff00", "dhash": "0f0f", "whash": "f0f0",
    }


class TestPartitionStale:
    def test_unknown_files_are_stale(self, cache, tmp_path):
        p = tmp_path / "a.png"
        _touch(p)
        fresh, stale = cache.partition_stale([str(p)], hash_size=16)
        assert fresh == {} and stale == [str(p)]

    def test_cached_file_is_fresh(self, cache, tmp_path):
        p = tmp_path / "a.png"
        _touch(p)
        cache.upsert_hashes([_record(p)], hash_size=16)
        fresh, stale = cache.partition_stale([str(p)], hash_size=16)
        assert str(p) in fresh and stale == []
        assert fresh[str(p)]["phash"] == "ff00"

    def test_modified_file_goes_stale(self, cache, tmp_path):
        p = tmp_path / "a.png"
        _touch(p)
        cache.upsert_hashes([_record(p)], hash_size=16)
        time.sleep(0.01)
        _touch(p, b"changed-content")
        fresh, stale = cache.partition_stale([str(p)], hash_size=16)
        assert fresh == {} and stale == [str(p)]

    def test_hash_size_change_goes_stale(self, cache, tmp_path):
        p = tmp_path / "a.png"
        _touch(p)
        cache.upsert_hashes([_record(p)], hash_size=16)
        fresh, stale = cache.partition_stale([str(p)], hash_size=32)
        assert fresh == {} and stale == [str(p)]

    def test_vanished_file_skipped(self, cache, tmp_path):
        fresh, stale = cache.partition_stale([str(tmp_path / "ghost.png")], 16)
        assert fresh == {} and stale == []


class TestEmbeddings:
    def test_roundtrip(self, cache, tmp_path):
        p = tmp_path / "a.png"
        _touch(p)
        cache.upsert_hashes([_record(p)], hash_size=16)
        vec = np.arange(8, dtype=np.float32)
        cache.upsert_embeddings({str(p): vec}, model="resnet18")
        have, missing = cache.get_embeddings([str(p)], model="resnet18")
        assert missing == []
        np.testing.assert_array_equal(have[str(p)], vec)

    def test_model_mismatch_is_missing(self, cache, tmp_path):
        p = tmp_path / "a.png"
        _touch(p)
        cache.upsert_hashes([_record(p)], hash_size=16)
        cache.upsert_embeddings({str(p): np.ones(4, np.float32)}, model="resnet18")
        _, missing = cache.get_embeddings([str(p)], model="openclip")
        assert missing == [str(p)]

    def test_rehash_clears_embedding(self, cache, tmp_path):
        p = tmp_path / "a.png"
        _touch(p)
        cache.upsert_hashes([_record(p)], hash_size=16)
        cache.upsert_embeddings({str(p): np.ones(4, np.float32)}, model="resnet18")
        cache.upsert_hashes([_record(p)], hash_size=16)  # simulated re-hash
        _, missing = cache.get_embeddings([str(p)], model="resnet18")
        assert missing == [str(p)]


class TestMaintenance:
    def test_prune_missing(self, cache, tmp_path):
        p1, p2 = tmp_path / "keep.png", tmp_path / "gone.png"
        _touch(p1)
        _touch(p2)
        cache.upsert_hashes([_record(p1), _record(p2)], hash_size=16)
        os.unlink(p2)
        assert cache.prune_missing() == 1
        assert cache.row_count() == 1
