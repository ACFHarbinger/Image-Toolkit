// ---------------------------------------------------------------------------
// base/benchmarks/bench_math.cpp
//
// Google Benchmark suite for base::math — the header-only math library:
//   • Distance metrics: euclidean, cosine, manhattan, minkowski, pairwise
//   • Descriptive statistics: mean, std_dev, pearson, z_score, histogram
//   • Information theory: shannon_entropy, KL divergence, JS divergence
//   • Graph algorithms: BFS, Kruskal MST, Tarjan SCC
//   • Linear algebra: Matrix multiply, PCA
//   • Dimensionality reduction: MDS
//
// Build:   cmake --build build/base --target base_bench_math
// Run:     ./build/base/benchmarks/base_bench_math --benchmark_format=json
// ---------------------------------------------------------------------------

#include <benchmark/benchmark.h>

#include "math/dim_reduce.hpp"
#include "math/distance.hpp"
#include "math/graph.hpp"
#include "math/information.hpp"
#include "math/linalg.hpp"
#include "math/stats.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <random>
#include <vector>

using namespace base::math;

// ---------------------------------------------------------------------------
// Seeded random data generators
// ---------------------------------------------------------------------------

namespace {

std::vector<double> rand_vec(std::size_t n, double lo = 0.0, double hi = 1.0,
                              unsigned seed = 42) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<double> dist(lo, hi);
    std::vector<double> v(n);
    for (auto& x : v) x = dist(rng);
    return v;
}

std::vector<double> rand_prob_vec(std::size_t n, unsigned seed = 42) {
    auto v = rand_vec(n, 0.01, 1.0, seed);
    double s = 0;
    for (auto x : v) s += x;
    for (auto& x : v) x /= s;
    return v;
}

std::vector<std::vector<double>> rand_matrix(int rows, int cols,
                                              unsigned seed = 7) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<double> dist(-1.0, 1.0);
    std::vector<std::vector<double>> m(rows, std::vector<double>(cols));
    for (auto& row : m)
        for (auto& x : row) x = dist(rng);
    return m;
}

// Uniform discrete distribution over k categories for MI benchmarks
std::vector<std::vector<std::size_t>> rand_joint_counts(int rows, int cols,
                                                         unsigned seed = 99) {
    std::mt19937 rng(seed);
    std::uniform_int_distribution<int> dist(0, 100);
    std::vector<std::vector<std::size_t>> m(rows, std::vector<std::size_t>(cols));
    for (auto& row : m)
        for (auto& x : row) x = static_cast<std::size_t>(dist(rng));
    return m;
}

} // namespace

// ---------------------------------------------------------------------------
// Distance metrics
// ---------------------------------------------------------------------------

static void BM_EuclideanDist(benchmark::State& state) {
    const std::size_t n = static_cast<std::size_t>(state.range(0));
    auto a = rand_vec(n, 0, 1, 1);
    auto b = rand_vec(n, 0, 1, 2);
    for (auto _ : state)
        benchmark::DoNotOptimize(euclidean(a, b));
    state.SetItemsProcessed(state.iterations() * static_cast<int64_t>(n));
}
BENCHMARK(BM_EuclideanDist)->Arg(64)->Arg(512)->Arg(4096)->Unit(benchmark::kNanosecond);

static void BM_CosineSimilarity(benchmark::State& state) {
    const std::size_t n = static_cast<std::size_t>(state.range(0));
    auto a = rand_vec(n, -1, 1, 3);
    auto b = rand_vec(n, -1, 1, 4);
    for (auto _ : state)
        benchmark::DoNotOptimize(cosine_similarity(a, b));
    state.SetItemsProcessed(state.iterations() * static_cast<int64_t>(n));
}
BENCHMARK(BM_CosineSimilarity)->Arg(64)->Arg(512)->Arg(4096)->Unit(benchmark::kNanosecond);

static void BM_ManhattanDist(benchmark::State& state) {
    const std::size_t n = static_cast<std::size_t>(state.range(0));
    auto a = rand_vec(n, 0, 1, 5);
    auto b = rand_vec(n, 0, 1, 6);
    for (auto _ : state)
        benchmark::DoNotOptimize(manhattan(a, b));
    state.SetItemsProcessed(state.iterations() * static_cast<int64_t>(n));
}
BENCHMARK(BM_ManhattanDist)->Arg(64)->Arg(512)->Arg(4096)->Unit(benchmark::kNanosecond);

static void BM_MinkowskiDist(benchmark::State& state) {
    const std::size_t n = static_cast<std::size_t>(state.range(0));
    auto a = rand_vec(n, 0, 1, 7);
    auto b = rand_vec(n, 0, 1, 8);
    for (auto _ : state)
        benchmark::DoNotOptimize(minkowski(a, b, 3.0));
    state.SetItemsProcessed(state.iterations() * static_cast<int64_t>(n));
}
BENCHMARK(BM_MinkowskiDist)->Arg(64)->Arg(512)->Unit(benchmark::kNanosecond);

static void BM_PairwiseDistMatrix(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));
    auto pts = rand_matrix(n, 64, 11);
    for (auto _ : state) {
        auto m = pairwise_distance_matrix(pts);
        benchmark::DoNotOptimize(m);
    }
    // Each call computes n*(n-1)/2 distances
    state.SetItemsProcessed(state.iterations() * (int64_t)n * (n - 1) / 2);
}
BENCHMARK(BM_PairwiseDistMatrix)->Arg(20)->Arg(50)->Arg(100)->Unit(benchmark::kMicrosecond);

// ---------------------------------------------------------------------------
// Descriptive statistics
// ---------------------------------------------------------------------------

static void BM_Mean(benchmark::State& state) {
    auto v = rand_vec(static_cast<std::size_t>(state.range(0)));
    for (auto _ : state) benchmark::DoNotOptimize(mean(v));
    state.SetItemsProcessed(state.iterations() * state.range(0));
}
BENCHMARK(BM_Mean)->Arg(100)->Arg(10000)->Arg(1000000)->Unit(benchmark::kNanosecond);

static void BM_StdDev(benchmark::State& state) {
    auto v = rand_vec(static_cast<std::size_t>(state.range(0)));
    for (auto _ : state) benchmark::DoNotOptimize(std_dev(v));
    state.SetItemsProcessed(state.iterations() * state.range(0));
}
BENCHMARK(BM_StdDev)->Arg(100)->Arg(10000)->Arg(1000000)->Unit(benchmark::kNanosecond);

static void BM_Pearson(benchmark::State& state) {
    const std::size_t n = static_cast<std::size_t>(state.range(0));
    auto a = rand_vec(n, 0, 1, 10);
    auto b = rand_vec(n, 0, 1, 11);
    for (auto _ : state) benchmark::DoNotOptimize(pearson(a, b));
    state.SetItemsProcessed(state.iterations() * static_cast<int64_t>(n));
}
BENCHMARK(BM_Pearson)->Arg(100)->Arg(10000)->Unit(benchmark::kNanosecond);

static void BM_ZScore(benchmark::State& state) {
    auto v = rand_vec(static_cast<std::size_t>(state.range(0)));
    for (auto _ : state) {
        auto r = z_score(v);
        benchmark::DoNotOptimize(r);
    }
    state.SetItemsProcessed(state.iterations() * state.range(0));
}
BENCHMARK(BM_ZScore)->Arg(1000)->Arg(100000)->Unit(benchmark::kMicrosecond);

static void BM_Histogram(benchmark::State& state) {
    const std::size_t n    = static_cast<std::size_t>(state.range(0));
    const std::size_t bins = 256;
    auto v = rand_vec(n, 0, 1, 42);
    for (auto _ : state) {
        auto [edges, counts] = histogram(v, bins);
        benchmark::DoNotOptimize(counts);
    }
    state.SetItemsProcessed(state.iterations() * static_cast<int64_t>(n));
}
BENCHMARK(BM_Histogram)->Arg(1000)->Arg(100000)->Unit(benchmark::kMicrosecond);

static void BM_CovarianceMatrix(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));
    const int d = 64;
    auto data = rand_matrix(n, d, 55);
    for (auto _ : state) {
        auto m = covariance_matrix(data);
        benchmark::DoNotOptimize(m);
    }
}
BENCHMARK(BM_CovarianceMatrix)->Arg(100)->Arg(500)->Unit(benchmark::kMillisecond);

// ---------------------------------------------------------------------------
// Information theory
// ---------------------------------------------------------------------------

static void BM_ShannonEntropy(benchmark::State& state) {
    auto p = rand_prob_vec(static_cast<std::size_t>(state.range(0)));
    for (auto _ : state) benchmark::DoNotOptimize(shannon_entropy(p));
    state.SetItemsProcessed(state.iterations() * state.range(0));
}
BENCHMARK(BM_ShannonEntropy)->Arg(64)->Arg(1024)->Arg(65536)->Unit(benchmark::kNanosecond);

static void BM_KLDivergence(benchmark::State& state) {
    const std::size_t n = static_cast<std::size_t>(state.range(0));
    auto p = rand_prob_vec(n, 1);
    auto q = rand_prob_vec(n, 2);
    for (auto _ : state) benchmark::DoNotOptimize(kl_divergence(p, q));
    state.SetItemsProcessed(state.iterations() * static_cast<int64_t>(n));
}
BENCHMARK(BM_KLDivergence)->Arg(64)->Arg(1024)->Arg(65536)->Unit(benchmark::kNanosecond);

static void BM_JSDivergence(benchmark::State& state) {
    const std::size_t n = static_cast<std::size_t>(state.range(0));
    auto p = rand_prob_vec(n, 3);
    auto q = rand_prob_vec(n, 4);
    for (auto _ : state) benchmark::DoNotOptimize(js_divergence(p, q));
    state.SetItemsProcessed(state.iterations() * static_cast<int64_t>(n));
}
BENCHMARK(BM_JSDivergence)->Arg(64)->Arg(1024)->Unit(benchmark::kNanosecond);

static void BM_MutualInformationDiscrete(benchmark::State& state) {
    const int rows = static_cast<int>(state.range(0));
    const int cols = rows;
    auto joint = rand_joint_counts(rows, cols);
    for (auto _ : state)
        benchmark::DoNotOptimize(mutual_information_discrete(joint));
}
BENCHMARK(BM_MutualInformationDiscrete)->Arg(8)->Arg(16)->Arg(32)->Unit(benchmark::kMicrosecond);

// ---------------------------------------------------------------------------
// Graph algorithms
// ---------------------------------------------------------------------------

/// Build a complete undirected graph on n nodes with random edge weights.
static Graph make_complete_graph(int n, unsigned seed = 77) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<double> dist(0.01, 10.0);
    Graph g(/*directed=*/false);
    for (int i = 0; i < n; ++i) g.add_node(i);
    for (int i = 0; i < n; ++i)
        for (int j = i + 1; j < n; ++j)
            g.add_edge(i, j, dist(rng));
    return g;
}

/// Build a DAG: edge from i → i+1 and i → i+2 (no cycles, toposortable).
static Graph make_dag(int n) {
    Graph g(/*directed=*/true);
    for (int i = 0; i < n; ++i) g.add_node(i);
    for (int i = 0; i + 1 < n; ++i) { g.add_edge(i, i + 1, 1.0); }
    for (int i = 0; i + 2 < n; ++i) { g.add_edge(i, i + 2, 0.5); }
    return g;
}

static void BM_BFS(benchmark::State& state) {
    auto g = make_complete_graph(static_cast<int>(state.range(0)));
    for (auto _ : state) {
        auto order = bfs(g, 0);
        benchmark::DoNotOptimize(order);
    }
}
BENCHMARK(BM_BFS)->Arg(50)->Arg(200)->Arg(500)->Unit(benchmark::kMicrosecond);

static void BM_DFS(benchmark::State& state) {
    auto g = make_complete_graph(static_cast<int>(state.range(0)));
    for (auto _ : state) {
        auto order = dfs(g, 0);
        benchmark::DoNotOptimize(order);
    }
}
BENCHMARK(BM_DFS)->Arg(50)->Arg(200)->Arg(500)->Unit(benchmark::kMicrosecond);

static void BM_KruskalMST(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));
    // Build edge list directly for the overload that takes n + vector<KruskalEdge>
    std::mt19937 rng(42);
    std::uniform_real_distribution<double> dist(0.01, 10.0);
    std::vector<KruskalEdge> edges;
    for (int i = 0; i < n; ++i)
        for (int j = i + 1; j < n; ++j)
            edges.push_back({i, j, dist(rng)});

    for (auto _ : state) {
        auto tree = kruskal_mst(n, edges);
        benchmark::DoNotOptimize(tree);
    }
    state.SetItemsProcessed(state.iterations() * static_cast<int64_t>(n * (n - 1) / 2));
}
BENCHMARK(BM_KruskalMST)->Arg(50)->Arg(100)->Arg(200)->Unit(benchmark::kMicrosecond);

static void BM_TarjanSCC(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));
    Graph g(/*directed=*/true);
    for (int i = 0; i < n; ++i) {
        g.add_node(i);
        g.add_edge(i, (i + 1) % n, 1.0);
        if (i % 5 == 0 && i + 3 < n)
            g.add_edge(i, i + 3, 0.5);
    }
    for (auto _ : state) {
        auto scc = tarjan_scc(g);
        benchmark::DoNotOptimize(scc);
    }
}
BENCHMARK(BM_TarjanSCC)->Arg(100)->Arg(500)->Arg(1000)->Unit(benchmark::kMicrosecond);

static void BM_TopoSort(benchmark::State& state) {
    auto g = make_dag(static_cast<int>(state.range(0)));
    for (auto _ : state) {
        auto order = topological_sort(g);
        benchmark::DoNotOptimize(order);
    }
}
BENCHMARK(BM_TopoSort)->Arg(100)->Arg(500)->Arg(1000)->Unit(benchmark::kMicrosecond);

// ---------------------------------------------------------------------------
// Linear algebra: Matrix operations & PCA
// ---------------------------------------------------------------------------

static void BM_MatrixMul(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));
    auto A = Matrix::from_rows(rand_matrix(n, n, 13));
    auto B = Matrix::from_rows(rand_matrix(n, n, 14));
    for (auto _ : state) {
        auto C = A.mul(B);
        benchmark::DoNotOptimize(C.data.data());
    }
    state.SetItemsProcessed(state.iterations() * static_cast<int64_t>(n) * n * n);
}
BENCHMARK(BM_MatrixMul)->Arg(32)->Arg(64)->Arg(128)->Unit(benchmark::kMillisecond);

static void BM_PCA(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));   // samples
    const int d = 64;                                  // features
    const int k = 8;                                   // components
    auto data = Matrix::from_rows(rand_matrix(n, d, 17));
    for (auto _ : state) {
        auto res = pca(data, k);
        benchmark::DoNotOptimize(res.scores.data.data());
    }
}
BENCHMARK(BM_PCA)->Arg(100)->Arg(500)->Arg(1000)->Unit(benchmark::kMillisecond);

// ---------------------------------------------------------------------------
// Dimensionality reduction: MDS
// ---------------------------------------------------------------------------

static void BM_MDS(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));
    // Build a symmetric n×n distance matrix
    std::mt19937 rng(23);
    std::uniform_real_distribution<double> dist(0.1, 5.0);
    Matrix D(n, n);
    for (int i = 0; i < n; ++i)
        for (int j = i + 1; j < n; ++j) {
            double d = dist(rng);
            D.set(i, j, d);
            D.set(j, i, d);
        }

    for (auto _ : state) {
        auto emb = mds(D, 2);
        benchmark::DoNotOptimize(emb.data.data());
    }
}
BENCHMARK(BM_MDS)->Arg(30)->Arg(60)->Arg(100)->Unit(benchmark::kMillisecond);
