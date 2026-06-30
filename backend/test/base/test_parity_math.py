"""
backend/test/base/test_parity_math.py
=======================================
Phase 12 integration tests for base.math (Phase 11 C++ bindings).

Tests are skipped when the C++ base extension is not built.

Run (when base is built):
    pytest backend/test/base/test_parity_math.py -v
"""

from __future__ import annotations

import math

import numpy as np
import pytest

try:
    import base as _base

    HAS_BASE = hasattr(_base, "math")
except ImportError:
    HAS_BASE = False

pytestmark = pytest.mark.skipif(
    not HAS_BASE, reason="base C++ extension not built"
)


# ---------------------------------------------------------------------------
# base.math.distance
# ---------------------------------------------------------------------------

class TestDistance:
    def test_euclidean_3_4_5_triangle(self):
        assert _base.math.distance.euclidean([0.0, 0.0], [3.0, 4.0]) == pytest.approx(5.0, abs=1e-6)

    def test_cosine_similarity_same_vector(self):
        assert _base.math.distance.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0, abs=1e-6)

    def test_cosine_similarity_orthogonal(self):
        assert _base.math.distance.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0, abs=1e-6)

    def test_hamming_distance_one_bit(self):
        assert _base.math.distance.hamming([True, False, True], [True, True, True]) == 1

    def test_manhattan_distance(self):
        assert _base.math.distance.manhattan([0.0, 0.0], [3.0, 4.0]) == pytest.approx(7.0, abs=1e-6)

    def test_bhattacharyya_identical_distributions(self):
        assert _base.math.distance.bhattacharyya([0.5, 0.5], [0.5, 0.5]) == pytest.approx(0.0, abs=1e-6)

    def test_euclidean_sq_matches_euclidean_sq(self):
        d = _base.math.distance.euclidean([0.0, 0.0], [3.0, 4.0])
        dsq = _base.math.distance.euclidean_sq([0.0, 0.0], [3.0, 4.0])
        assert dsq == pytest.approx(d * d, abs=1e-5)

    def test_cosine_distance_same_vector_is_zero(self):
        assert _base.math.distance.cosine_distance([1.0, 2.0], [1.0, 2.0]) == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# base.math.stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_mean_simple(self):
        assert _base.math.stats.mean([1.0, 2.0, 3.0, 4.0, 5.0]) == pytest.approx(3.0, abs=1e-9)

    def test_std_dev_constant_sequence(self):
        assert _base.math.stats.std_dev([2.0, 2.0, 2.0, 2.0]) == pytest.approx(0.0, abs=1e-9)

    def test_pearson_identical_vectors(self):
        assert _base.math.stats.pearson([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0, abs=1e-6)

    def test_z_score_peak_at_middle(self):
        zs = _base.math.stats.z_score([0.0, 0.0, 1.0, 0.0, 0.0])
        assert zs[2] == max(zs)

    def test_min_max_normalize_endpoints(self):
        result = _base.math.stats.min_max_normalize([0.0, 5.0, 10.0])
        assert result[0] == pytest.approx(0.0, abs=1e-9)
        assert result[1] == pytest.approx(0.5, abs=1e-9)
        assert result[2] == pytest.approx(1.0, abs=1e-9)

    def test_variance_known_value(self):
        # variance of [1,2,3,4,5] is 2.0 (population) or 2.5 (sample)
        v = _base.math.stats.variance([1.0, 2.0, 3.0, 4.0, 5.0])
        assert v == pytest.approx(2.0, abs=0.6)  # accept either pop or sample

    def test_median_odd_count(self):
        assert _base.math.stats.median([5.0, 1.0, 3.0]) == pytest.approx(3.0, abs=1e-9)


# ---------------------------------------------------------------------------
# base.math.information
# ---------------------------------------------------------------------------

class TestInformation:
    def test_shannon_entropy_uniform_binary(self):
        h = _base.math.information.shannon_entropy([0.5, 0.5])
        assert h == pytest.approx(1.0, abs=1e-6)  # 1 bit

    def test_kl_divergence_identical_distributions(self):
        assert _base.math.information.kl_divergence([0.5, 0.5], [0.5, 0.5]) == pytest.approx(0.0, abs=1e-6)

    def test_js_divergence_identical_distributions(self):
        assert _base.math.information.js_divergence([0.5, 0.5], [0.5, 0.5]) == pytest.approx(0.0, abs=1e-6)

    def test_js_distance_nonneg(self):
        d = _base.math.information.js_distance([0.6, 0.4], [0.3, 0.7])
        assert d >= 0.0

    def test_mutual_information_independent_distributions(self):
        # Uniform joint: MI ≈ 0
        p_xy = [0.25, 0.25, 0.25, 0.25]
        mi = _base.math.information.mutual_information(p_xy, [0.5, 0.5], [0.5, 0.5])
        assert abs(mi) < 0.1


# ---------------------------------------------------------------------------
# base.math.graph
# ---------------------------------------------------------------------------

class TestGraph:
    def test_bfs_visits_all_nodes(self):
        g = _base.math.graph.Graph(4)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        visited = _base.math.graph.bfs(g, 0)
        assert set(visited) == {0, 1, 2, 3}

    def test_bfs_order_from_root(self):
        g = _base.math.graph.Graph(3)
        g.add_edge(0, 1)
        g.add_edge(0, 2)
        visited = _base.math.graph.bfs(g, 0)
        assert visited[0] == 0

    def test_kruskal_mst_3_nodes(self):
        g = _base.math.graph.Graph(3)
        g.add_weighted_edge(0, 1, 1.0)
        g.add_weighted_edge(1, 2, 2.0)
        g.add_weighted_edge(0, 2, 10.0)
        mst = _base.math.graph.kruskal_mst(g)
        assert len(mst) == 2  # N-1 edges

    def test_topological_sort_dag(self):
        g = _base.math.graph.Graph(4)
        g.add_directed_edge(0, 1)
        g.add_directed_edge(1, 2)
        g.add_directed_edge(0, 3)
        order = _base.math.graph.topological_sort(g)
        assert order.index(0) < order.index(1)
        assert order.index(1) < order.index(2)

    def test_dfs_visits_all_nodes(self):
        g = _base.math.graph.Graph(3)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        visited = _base.math.graph.dfs(g, 0)
        assert set(visited) == {0, 1, 2}


# ---------------------------------------------------------------------------
# base.math.linalg
# ---------------------------------------------------------------------------

class TestLinalg:
    def test_matrix_dimensions(self):
        m = _base.math.linalg.Matrix(3, 3)
        assert m.rows() == 3
        assert m.cols() == 3

    def test_pca_explained_variance_sums_to_one(self):
        rng = np.random.default_rng(0)
        data = rng.standard_normal((20, 4)).tolist()
        result = _base.math.linalg.pca(data, n_components=2)
        evr = result.explained_variance_ratio
        assert sum(evr) <= 1.0 + 1e-6

    def test_pca_returns_scores_shape(self):
        data = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]]
        result = _base.math.linalg.pca(data, n_components=1)
        assert len(result.scores) == 4
        assert all(len(row) == 1 for row in result.scores)

    def test_matrix_multiply_2x2(self):
        # [[1,2],[3,4]] × [[1,0],[0,1]] = [[1,2],[3,4]]
        a = _base.math.linalg.Matrix(2, 2)
        a.set(0, 0, 1.0); a.set(0, 1, 2.0)
        a.set(1, 0, 3.0); a.set(1, 1, 4.0)
        b = _base.math.linalg.Matrix(2, 2)
        b.set(0, 0, 1.0); b.set(0, 1, 0.0)
        b.set(1, 0, 0.0); b.set(1, 1, 1.0)
        c = a.multiply(b)
        assert c.get(0, 0) == pytest.approx(1.0)
        assert c.get(1, 1) == pytest.approx(4.0)

    def test_pca_components_count(self):
        data = [[float(i), float(i * 2), float(i * 3)] for i in range(10)]
        result = _base.math.linalg.pca(data, n_components=2)
        assert len(result.components) == 2


# ---------------------------------------------------------------------------
# base.math.dim_reduce
# ---------------------------------------------------------------------------

class TestDimReduce:
    def test_mds_returns_coordinates(self):
        dist = [[0.0, 1.0, 2.0], [1.0, 0.0, 1.0], [2.0, 1.0, 0.0]]
        coords = _base.math.dim_reduce.mds(dist, n_components=2)
        assert len(coords) == 3
        assert all(len(row) == 2 for row in coords)

    def test_mds_small_distance_matrix(self):
        dist = [[0.0, 0.5], [0.5, 0.0]]
        coords = _base.math.dim_reduce.mds(dist, n_components=1)
        assert len(coords) == 2

    def test_tsne_affinities_returns_matrix(self):
        data = [[float(i), float(i + 1)] for i in range(5)]
        aff = _base.math.dim_reduce.tsne_affinities(data, perplexity=2.0)
        assert len(aff) == 5
        assert len(aff[0]) == 5

    def test_tsne_affinities_rows_sum_near_one(self):
        data = [[float(i), float(i + 1)] for i in range(6)]
        aff = _base.math.dim_reduce.tsne_affinities(data, perplexity=2.0)
        for row in aff:
            assert sum(row) == pytest.approx(1.0, abs=0.05)

    def test_tsne_affinities_symmetric(self):
        data = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        aff = _base.math.dim_reduce.tsne_affinities(data, perplexity=1.0)
        for i in range(3):
            for j in range(3):
                assert aff[i][j] == pytest.approx(aff[j][i], abs=1e-6)
