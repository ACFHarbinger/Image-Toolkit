"""C++ base.recon.IdentityIndex + cutout_hash tests."""

import numpy as np
import pytest

base = pytest.importorskip("base")
recon = base.recon


def _clustered(n_people=4, per=5, dim=32, seed=0):
    rng = np.random.default_rng(seed)
    centers = {f"Person_{i}": rng.normal(size=dim) for i in range(n_people)}
    vecs, labels, paths = [], [], []
    for name, c in centers.items():
        for j in range(per):
            vecs.append((c + 0.02 * rng.normal(size=dim)).astype(np.float32))
            labels.append(name)
            paths.append(f"/Data/{name}/img{j}.jpg")
    return np.stack(vecs), labels, paths, centers


class TestIdentityIndex:
    def test_add_and_size(self):
        idx = recon.IdentityIndex(dim=16)
        idx.add(np.ones(16, np.float32).tolist(), "A_B", "/Data/A_B/1.jpg")
        assert idx.size == 1
        assert idx.labels() == ["A_B"]

    def test_add_batch_resolves_identity(self):
        vecs, labels, paths, centers = _clustered()
        idx = recon.IdentityIndex(dim=vecs.shape[1])
        idx.add_batch(vecs, labels, paths)
        assert idx.size == len(labels)
        q = (centers["Person_2"] + 0.01).astype(np.float32)
        res = idx.query(q.tolist(), k=3)
        assert res[0][0] == "Person_2"
        assert res[0][2] > 0.9

    def test_query_returns_distinct_labels(self):
        vecs, labels, paths, centers = _clustered()
        idx = recon.IdentityIndex(dim=vecs.shape[1])
        idx.add_batch(vecs, labels, paths)
        res = idx.query(centers["Person_0"].astype(np.float32).tolist(), k=4)
        seen = [label for label, _p, _s in res]
        assert len(seen) == len(set(seen))   # no duplicate identities

    def test_batch_length_mismatch_raises(self):
        idx = recon.IdentityIndex(dim=8)
        with pytest.raises(ValueError):
            idx.add_batch(np.zeros((2, 8), np.float32), ["a"], ["p1", "p2"])


class TestCutoutHash:
    def test_stable_and_distinct(self):
        assert recon.cutout_hash(b"abc") == recon.cutout_hash(b"abc")
        assert recon.cutout_hash(b"abc") != recon.cutout_hash(b"abd")

    def test_hex_length(self):
        assert len(recon.cutout_hash(b"anything")) == 16
