// ---------------------------------------------------------------------------
// batch/tests/math/test_math.cpp
//
// Catch2 unit tests for the base::math header-only library.
// All headers are fully implemented — these tests run without stubs.
// ---------------------------------------------------------------------------

#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>

#include "math/distance.hpp"
#include "math/stats.hpp"
#include "math/information.hpp"
#include "math/graph.hpp"
#include "math/linalg.hpp"
#include "math/dim_reduce.hpp"

#include <cmath>
#include <numeric>

using Approx = Catch::Approx;
namespace bm = base::math;

// ===========================================================================
// distance.hpp
// ===========================================================================

TEST_CASE("euclidean: basic", "[math][distance]") {
    CHECK(bm::euclidean({0, 0}, {3, 4}) == Approx(5.0));
    CHECK(bm::euclidean({1, 2, 3}, {1, 2, 3}) == Approx(0.0));
}

TEST_CASE("euclidean_sq: no sqrt", "[math][distance]") {
    CHECK(bm::euclidean_sq({0, 0}, {3, 4}) == Approx(25.0));
}

TEST_CASE("cosine_similarity: identical vectors → 1", "[math][distance]") {
    CHECK(bm::cosine_similarity({1, 2, 3}, {1, 2, 3}) == Approx(1.0));
}

TEST_CASE("cosine_similarity: orthogonal vectors → 0", "[math][distance]") {
    CHECK(bm::cosine_similarity({1, 0}, {0, 1}) == Approx(0.0));
}

TEST_CASE("cosine_distance: distance of identical vectors → 0", "[math][distance]") {
    CHECK(bm::cosine_distance({1, 1}, {1, 1}) == Approx(0.0));
}

TEST_CASE("hamming: counts differing bits", "[math][distance]") {
    CHECK(bm::hamming({true, false, true}, {false, false, true}) == 1);
    CHECK(bm::hamming({true, true}, {true, true}) == 0);
}

TEST_CASE("bhattacharyya: identical distributions → 0", "[math][distance]") {
    std::vector<double> p{0.5, 0.5};
    CHECK(bm::bhattacharyya(p, p) == Approx(0.0).margin(1e-10));
}

TEST_CASE("hellinger: identical distributions → 0", "[math][distance]") {
    std::vector<double> p{0.25, 0.25, 0.25, 0.25};
    CHECK(bm::hellinger(p, p) == Approx(0.0).margin(1e-10));
}

TEST_CASE("manhattan: L1 distance", "[math][distance]") {
    CHECK(bm::manhattan({0, 0}, {3, 4}) == Approx(7.0));
}

// ===========================================================================
// stats.hpp
// ===========================================================================

TEST_CASE("mean: arithmetic mean", "[math][stats]") {
    CHECK(bm::mean({1, 2, 3, 4, 5}) == Approx(3.0));
}

TEST_CASE("median: even and odd length", "[math][stats]") {
    CHECK(bm::median({3, 1, 2}) == Approx(2.0));
    CHECK(bm::median({1, 2, 3, 4}) == Approx(2.5));
}

TEST_CASE("std_dev: known standard deviation", "[math][stats]") {
    // std_dev({2,4,4,4,5,5,7,9}, ddof=0) = 2.0
    CHECK(bm::std_dev({2,4,4,4,5,5,7,9}, 0) == Approx(2.0));
}

TEST_CASE("pearson: perfect correlation → 1", "[math][stats]") {
    CHECK(bm::pearson({1,2,3}, {2,4,6}) == Approx(1.0));
}

TEST_CASE("pearson: perfect anti-correlation → -1", "[math][stats]") {
    CHECK(bm::pearson({1,2,3}, {3,2,1}) == Approx(-1.0));
}

TEST_CASE("z_score: mean 0 and std 1 after transform", "[math][stats]") {
    auto z = bm::z_score({2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0});
    double zm = bm::mean(z);
    CHECK(zm == Approx(0.0).margin(1e-10));
    CHECK(bm::std_dev(z, 1) == Approx(1.0).margin(1e-10));
}

TEST_CASE("min_max_normalize: output in [0,1]", "[math][stats]") {
    auto n = bm::min_max_normalize({10, 20, 30, 40, 50});
    CHECK(n.front() == Approx(0.0));
    CHECK(n.back()  == Approx(1.0));
}

// ===========================================================================
// information.hpp
// ===========================================================================

TEST_CASE("shannon_entropy: uniform distribution is maximal", "[math][info]") {
    std::vector<double> uniform(8, 1.0 / 8.0);
    CHECK(bm::shannon_entropy(uniform) == Approx(3.0));  // log2(8)
}

TEST_CASE("shannon_entropy: deterministic distribution → 0", "[math][info]") {
    CHECK(bm::shannon_entropy({1.0, 0.0, 0.0}) == Approx(0.0).margin(1e-10));
}

TEST_CASE("kl_divergence: identical distributions → 0", "[math][info]") {
    std::vector<double> p{0.5, 0.5};
    CHECK(bm::kl_divergence(p, p) == Approx(0.0).margin(1e-10));
}

TEST_CASE("js_divergence: symmetric", "[math][info]") {
    std::vector<double> p{0.7, 0.3}, q{0.3, 0.7};
    CHECK(bm::js_divergence(p, q) == Approx(bm::js_divergence(q, p)).margin(1e-10));
}

TEST_CASE("js_divergence: identical → 0", "[math][info]") {
    std::vector<double> p{0.5, 0.5};
    CHECK(bm::js_divergence(p, p) == Approx(0.0).margin(1e-10));
}

TEST_CASE("mutual_information: independent variables → 0", "[math][info]") {
    // P(X=0,Y=0)=0.25 etc. — joint = product of marginals
    std::vector<std::vector<double>> joint{{0.25, 0.25}, {0.25, 0.25}};
    CHECK(bm::mutual_information(joint) == Approx(0.0).margin(1e-10));
}

// ===========================================================================
// graph.hpp
// ===========================================================================

TEST_CASE("Graph: add_node and add_edge", "[math][graph]") {
    bm::Graph g(false);
    g.add_node(0, "A");
    g.add_node(1, "B");
    g.add_edge(0, 1, 2.5);
    CHECK(g.node_count() == 2);
    CHECK(g.neighbors(0).size() == 1);
    CHECK(g.neighbors(0)[0].dst == 1);
    CHECK(g.neighbors(0)[0].weight == Approx(2.5));
}

TEST_CASE("bfs: discovers all reachable nodes", "[math][graph]") {
    bm::Graph g(false);
    for (int i = 0; i < 4; ++i) g.add_node(i);
    g.add_edge(0,1); g.add_edge(1,2); g.add_edge(2,3);
    auto order = bm::bfs(g, 0);
    CHECK(order.size() == 4);
    CHECK(order[0] == 0);
}

TEST_CASE("dfs: discovers all reachable nodes", "[math][graph]") {
    bm::Graph g(false);
    for (int i = 0; i < 4; ++i) g.add_node(i);
    g.add_edge(0,1); g.add_edge(1,2); g.add_edge(2,3);
    auto order = bm::dfs(g, 0);
    CHECK(order.size() == 4);
}

TEST_CASE("kruskal_mst: minimum spanning tree has n-1 edges", "[math][graph]") {
    // Complete graph on 4 nodes
    std::vector<bm::KruskalEdge> edges{
        {0,1,1},{0,2,4},{0,3,3},{1,2,2},{1,3,5},{2,3,6}
    };
    auto mst = bm::kruskal_mst(4, edges);
    CHECK(mst.size() == 3);
    double total = 0;
    for (const auto& e : mst) total += e.weight;
    CHECK(total == Approx(6.0));  // 1+2+3
}

TEST_CASE("kruskal_max_mst: maximum spanning tree", "[math][graph]") {
    std::vector<bm::KruskalEdge> edges{{0,1,1},{0,2,4},{1,2,2}};
    auto mst = bm::kruskal_max_mst(3, edges);
    CHECK(mst.size() == 2);
    double total = 0;
    for (const auto& e : mst) total += e.weight;
    CHECK(total == Approx(6.0));  // 4+2
}

TEST_CASE("UnionFind: connect and query", "[math][graph]") {
    bm::UnionFind uf(5);
    CHECK_FALSE(uf.connected(0, 4));
    uf.unite(0, 1); uf.unite(1, 2);
    CHECK(uf.connected(0, 2));
    CHECK_FALSE(uf.connected(0, 3));
}

TEST_CASE("tarjan_scc: single SCC in complete directed graph", "[math][graph]") {
    bm::Graph g(true);
    for (int i = 0; i < 3; ++i) g.add_node(i);
    g.add_edge(0,1); g.add_edge(1,2); g.add_edge(2,0);
    auto scc = bm::tarjan_scc(g);
    CHECK(scc.components.size() == 1);
    CHECK(scc.components[0].size() == 3);
}

TEST_CASE("topological_sort: DAG ordered correctly", "[math][graph]") {
    bm::Graph g(true);
    for (int i = 0; i < 4; ++i) g.add_node(i);
    g.add_edge(0,1); g.add_edge(0,2); g.add_edge(1,3); g.add_edge(2,3);
    auto order = bm::topological_sort(g);
    REQUIRE(order.size() == 4);
    // 0 must come before 1,2; 1,2 before 3
    auto pos = [&](int v){ return std::distance(order.begin(), std::find(order.begin(),order.end(),v)); };
    CHECK(pos(0) < pos(1));
    CHECK(pos(0) < pos(2));
    CHECK(pos(1) < pos(3));
    CHECK(pos(2) < pos(3));
}

// ===========================================================================
// linalg.hpp
// ===========================================================================

TEST_CASE("Matrix: identity diagonal is all 1", "[math][linalg]") {
    auto I = bm::Matrix::identity(3);
    for (int i = 0; i < 3; ++i)
        for (int j = 0; j < 3; ++j)
            CHECK(I.get(i,j) == Approx(i == j ? 1.0 : 0.0));
}

TEST_CASE("Matrix: transpose swaps rows and cols", "[math][linalg]") {
    auto M = bm::Matrix::from_rows({{1,2,3},{4,5,6}});
    auto T = M.transpose();
    CHECK(T.rows() == 3);
    CHECK(T.cols() == 2);
    CHECK(T.get(0,1) == Approx(4.0));
}

TEST_CASE("Matrix: mul is correct", "[math][linalg]") {
    auto A = bm::Matrix::from_rows({{1,2},{3,4}});
    auto B = bm::Matrix::identity(2);
    auto C = A.mul(B);
    CHECK(C.get(0,0) == Approx(1.0));
    CHECK(C.get(1,1) == Approx(4.0));
}

TEST_CASE("pca: explained variance ratios sum to <= 1", "[math][linalg]") {
    // Random-ish data (5 samples, 4 features)
    auto M = bm::Matrix::from_rows({
        {1.0, 2.0, 3.0, 4.0},
        {2.0, 3.0, 4.0, 5.0},
        {3.0, 4.0, 5.0, 6.0},
        {4.0, 5.0, 6.0, 7.0},
        {5.0, 6.0, 7.0, 8.0},
    });
    auto result = bm::pca(M, 2);
    double total = 0;
    for (double r : result.explained_variance_ratio) total += r;
    CHECK(total <= 1.0 + 1e-9);
    CHECK(result.scores.rows() == 5);
    CHECK(result.scores.cols() == 2);
}

// ===========================================================================
// dim_reduce.hpp
// ===========================================================================

TEST_CASE("mds: output shape is correct", "[math][dim_reduce]") {
    // 4×4 symmetric distance matrix
    auto D = bm::Matrix::from_rows({
        {0.0, 1.0, 2.0, 3.0},
        {1.0, 0.0, 1.0, 2.0},
        {2.0, 1.0, 0.0, 1.0},
        {3.0, 2.0, 1.0, 0.0},
    });
    auto E = bm::mds(D, 2);
    CHECK(E.rows() == 4);
    CHECK(E.cols() == 2);
}

TEST_CASE("mds: zero distance matrix → near-zero embedding", "[math][dim_reduce]") {
    auto D = bm::Matrix(4, 4);  // all zeros
    auto E = bm::mds(D, 2);
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 2; ++j)
            CHECK(std::abs(E.get(i,j)) < 1e-9);
}

TEST_CASE("tsne_affinities: output is symmetric", "[math][dim_reduce]") {
    auto data = bm::Matrix::from_rows({
        {1.0, 0.0}, {0.0, 1.0}, {-1.0, 0.0}, {0.0, -1.0}, {0.0, 0.0}
    });
    auto P = bm::tsne_affinities(data, 2.0);
    CHECK(P.rows() == 5);
    CHECK(P.cols() == 5);
    for (int i = 0; i < 5; ++i)
        for (int j = 0; j < 5; ++j)
            CHECK(P.get(i,j) == Approx(P.get(j,i)).margin(1e-10));
}

TEST_CASE("tsne_affinities: diagonal is zero", "[math][dim_reduce]") {
    auto data = bm::Matrix::from_rows({
        {1.0, 0.0}, {0.0, 1.0}, {-1.0, 0.0}, {0.0, -1.0}, {0.0, 0.0}
    });
    auto P = bm::tsne_affinities(data, 2.0);
    for (int i = 0; i < 5; ++i)
        CHECK(P.get(i,i) == Approx(0.0).margin(1e-10));
}
