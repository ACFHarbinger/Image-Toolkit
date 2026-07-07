"""Invariant tests for the C++ base.similarity primitives."""

import numpy as np
import pytest

base = pytest.importorskip("base")
sim = base.similarity


class TestXxHash:
    def test_identical_files_same_digest(self, image_dir):
        a = sim.xxh64_file(str(image_dir / "base.png"))
        b = sim.xxh64_file(str(image_dir / "copy_exact.png"))
        assert a and a == b

    def test_different_files_differ(self, image_dir):
        assert sim.xxh64_file(str(image_dir / "base.png")) != sim.xxh64_file(
            str(image_dir / "unrelated1.png")
        )

    def test_missing_file_empty(self):
        assert sim.xxh64_file("/nonexistent/nope.png") == ""

    def test_batch_matches_single(self, image_dir):
        paths = [str(image_dir / "base.png"), str(image_dir / "unrelated1.png")]
        assert sim.xxh64_files(paths) == [sim.xxh64_file(p) for p in paths]


class TestPerceptualHashes:
    @pytest.mark.parametrize("hash_size", [8, 16, 32])
    def test_hash_lengths(self, image_dir, hash_size):
        recs = sim.compute_hashes([str(image_dir / "base.png")], hash_size=hash_size)
        assert recs[0]["ok"]
        expected_hex = (hash_size * hash_size) // 4
        for key in ("phash", "dhash", "whash"):
            assert len(recs[0][key]) == expected_hex

    def test_resized_copy_close(self, image_dir):
        recs = sim.compute_hashes(
            [str(image_dir / "base.png"), str(image_dir / "copy_resized.png")],
            hash_size=16,
        )
        dist = sim.hamming(recs[0]["phash"], recs[1]["phash"])
        assert dist <= 16  # far under the 256-bit total

    def test_unrelated_far(self, image_dir):
        recs = sim.compute_hashes(
            [str(image_dir / "base.png"), str(image_dir / "unrelated1.png")],
            hash_size=16,
        )
        assert sim.hamming(recs[0]["phash"], recs[1]["phash"]) > 40

    def test_consensus_confidence_bounds(self, image_dir):
        recs = sim.compute_hashes(
            [str(image_dir / "base.png"), str(image_dir / "copy_bright.jpg")],
            hash_size=16,
        )
        a, b = recs
        conf_same = sim.consensus_confidence(
            a["phash"], a["dhash"], a["whash"],
            a["phash"], a["dhash"], a["whash"], hash_size=16,
        )
        conf_pair = sim.consensus_confidence(
            a["phash"], a["dhash"], a["whash"],
            b["phash"], b["dhash"], b["whash"], hash_size=16,
        )
        assert conf_same == pytest.approx(1.0)
        assert 0.0 <= conf_pair <= 1.0
        assert conf_pair > 0.8  # brightness shift stays similar


class TestVpTree:
    def test_matches_brute_force(self):
        rng = np.random.default_rng(7)
        hashes = [f"{rng.integers(0, 2**63):016x}" for _ in range(200)]
        tree = sim.VpTree(hashes)
        radius = 12
        got = {(min(i, j), max(i, j)) for i, j, _ in tree.pairs_within(radius)}
        want = set()
        for i in range(len(hashes)):
            for j in range(i + 1, len(hashes)):
                if sim.hamming(hashes[i], hashes[j]) <= radius:
                    want.add((i, j))
        assert got == want

    def test_query_self(self):
        tree = sim.VpTree(["00000000000000ff", "ffffffffffffffff"])
        hits = tree.query("00000000000000ff", 0)
        assert hits == [(0, 0)]


class TestHnsw:
    def test_recall_against_bruteforce(self):
        rng = np.random.default_rng(3)
        vecs = rng.normal(size=(300, 32)).astype(np.float32)
        index = sim.HnswIndex(dim=32, M=16, ef_construction=200)
        index.add_items(vecs)
        assert index.size == 300

        norm = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
        sims = norm @ norm.T
        hit = 0
        for q in range(50):
            true_nn = int(np.argsort(-sims[q])[1])  # skip self
            got = [i for i, _ in index.knn(vecs[q].tolist(), k=3, ef_search=128)]
            assert got[0] == q  # self is nearest
            if true_nn in got:
                hit += 1
        assert hit >= 45  # ≥90 % top-3 recall

    def test_pairs_within_finds_near_duplicate(self):
        rng = np.random.default_rng(5)
        vecs = rng.normal(size=(50, 16)).astype(np.float32)
        vecs[20] = vecs[4] + 1e-5
        index = sim.HnswIndex(dim=16)
        index.add_items(vecs)
        pairs = {(i, j) for i, j, s in index.pairs_within(0.999)}
        assert (4, 20) in pairs


class TestVisual:
    def test_ssim_self_is_one(self, image_dir):
        p = str(image_dir / "base.png")
        assert sim.ssim(p, p) == pytest.approx(1.0, abs=1e-6)

    def test_ssim_unrelated_lower(self, image_dir):
        s = sim.ssim(str(image_dir / "base.png"), str(image_dir / "unrelated1.png"))
        assert s < 0.5

    def test_match_features_self(self, image_dir):
        r = sim.match_features(str(image_dir / "base.png"), str(image_dir / "base.png"))
        assert r["ok"]
        assert r["confidence"] > 0.5
        assert r["inliers"] > 10

    def test_match_features_missing_file(self):
        r = sim.match_features("/nope/a.png", "/nope/b.png")
        assert not r["ok"]

    def test_diff_mask(self, image_dir, tmp_path):
        out = str(tmp_path / "diff.png")
        r = sim.diff_mask(
            str(image_dir / "base.png"), str(image_dir / "unrelated1.png"), out
        )
        assert r["ok"]
        assert r["out_path"] == out
        assert 0.0 < r["changed_ratio"] <= 1.0

    def test_diff_mask_identical(self, image_dir, tmp_path):
        out = str(tmp_path / "diff0.png")
        p = str(image_dir / "base.png")
        r = sim.diff_mask(p, p, out)
        assert r["ok"]
        assert r["changed_ratio"] == pytest.approx(0.0)
