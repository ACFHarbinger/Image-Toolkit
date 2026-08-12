#include <benchmark/benchmark.h>

#include <random>
#include <vector>

#include "exact_solvers.hpp"
#include "metaheuristics.hpp"

using namespace hybrid_image_editor;

// ─── Seam Routing (DP) ──────────────────────────────────────────────────────

static std::vector<SeamPixel> make_energy_grid(std::size_t rows, std::size_t cols) {
    std::mt19937 rng(42);
    std::uniform_real_distribution<float> energy_dist(0.f, 1.f);
    std::vector<SeamPixel> grid(rows * cols);
    for (auto& px : grid) {
        px.energy = energy_dist(rng);
        px.masked = false;
    }
    return grid;
}

static void BM_SolveSeam(benchmark::State& state) {
    const auto rows = static_cast<std::size_t>(state.range(0));
    const auto cols = static_cast<std::size_t>(state.range(1));
    auto grid = make_energy_grid(rows, cols);
    for (auto _ : state) {
        benchmark::DoNotOptimize(solve_seam(grid, rows, cols));
    }
}
BENCHMARK(BM_SolveSeam)->Args({256, 256})->Args({1080, 1920});

// ─── GNC-TLS Alignment ──────────────────────────────────────────────────────

static std::vector<Correspondence> make_correspondences(std::size_t n, std::size_t n_outliers) {
    std::vector<Correspondence> corrs;
    corrs.reserve(n);
    for (std::size_t i = 0; i < n - n_outliers; ++i) {
        Correspondence c;
        c.src_x = static_cast<float>(i * 15);
        c.src_y = static_cast<float>(i * 8);
        c.dst_x = c.src_x + 10.f;
        c.dst_y = c.src_y - 5.f;
        corrs.push_back(c);
    }
    for (std::size_t i = 0; i < n_outliers; ++i) {
        corrs.push_back(Correspondence{100.f * static_cast<float>(i), 50.f * static_cast<float>(i),
                                        9999.f, -9999.f});
    }
    return corrs;
}

static void BM_SolveAlignmentGnc(benchmark::State& state) {
    const auto n = static_cast<std::size_t>(state.range(0));
    auto corrs = make_correspondences(n, n / 10);
    for (auto _ : state) {
        benchmark::DoNotOptimize(solve_alignment_gnc(corrs));
    }
}
BENCHMARK(BM_SolveAlignmentGnc)->Arg(50)->Arg(500)->Arg(5000);

// ─── Convex Color Harmonization ─────────────────────────────────────────────

static void BM_SolveColorHarmonization(benchmark::State& state) {
    LayerColorStats source{40.f, 1.f, 2.f, 10.f, 5.f, 5.f};
    LayerColorStats target{60.f, 3.f, -2.f, 20.f, 15.f, 10.f};
    for (auto _ : state) {
        benchmark::DoNotOptimize(solve_color_harmonization(source, target));
    }
}
BENCHMARK(BM_SolveColorHarmonization);

// ─── Metaheuristics (PSO / DE) ──────────────────────────────────────────────
//
// Rosenbrock — the same non-convex, narrow-valley test function used by
// middleware/scripts/benchmark_jobs.py's Python-level report, so results are
// directly comparable across the native/reference boundary.

static float rosenbrock(const std::vector<float>& p) {
    float sum = 0.f;
    for (std::size_t i = 0; i + 1 < p.size(); ++i) {
        const float t1 = p[i + 1] - p[i] * p[i];
        const float t2 = 1.f - p[i];
        sum += 100.f * t1 * t1 + t2 * t2;
    }
    return sum;
}

static void BM_PsoSolve(benchmark::State& state) {
    const auto dim = static_cast<std::size_t>(state.range(0));
    std::vector<ParamBound> bounds(dim, ParamBound{-5.f, 5.f});
    for (auto _ : state) {
        benchmark::DoNotOptimize(pso_solve(rosenbrock, bounds));
    }
}
BENCHMARK(BM_PsoSolve)->Arg(2)->Arg(6);

static void BM_DeSolve(benchmark::State& state) {
    const auto dim = static_cast<std::size_t>(state.range(0));
    std::vector<ParamBound> bounds(dim, ParamBound{-5.f, 5.f});
    for (auto _ : state) {
        benchmark::DoNotOptimize(de_solve(rosenbrock, bounds));
    }
}
BENCHMARK(BM_DeSolve)->Arg(2)->Arg(6);
