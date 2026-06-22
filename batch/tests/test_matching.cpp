// ---------------------------------------------------------------------------
// batch/tests/test_matching.cpp
//
// Native C++ unit tests for batch::matching functions.
//
// Tests (pure C++ — no Python references):
//   phase_correlate_masked : output struct keys present, zero-shift for
//                            identical frames, known-shift detection,
//                            response clamped to [0,1]
//   reject_static_edges    : removes small-displacement edges,
//                            keeps large-displacement edges
//   compute_adaptive_min_disp : returns positive value, larger edges →
//                               larger threshold
//
// Tagged [not_impl]; REQUIRE_THROWS_AS until Phase 3.
// ---------------------------------------------------------------------------

#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <stdexcept>
#include <vector>
#include <cmath>

// ---------------------------------------------------------------------------
// POD types (matching affine_types.hpp Edge)
// ---------------------------------------------------------------------------
struct Edge {
    int   i, j;
    float dx, dy, weight;
};

struct PhaseResult {
    float dx, dy, response;
};

// ---------------------------------------------------------------------------
// Forward declarations of impl functions (matching.cpp)
// ---------------------------------------------------------------------------
PhaseResult phase_correlate_masked_impl(
    const cv::Mat& frame_a_gray,
    const cv::Mat& frame_b_gray,
    const cv::Mat& mask_a,   // may be empty
    const cv::Mat& mask_b);

std::vector<Edge> reject_static_edges_impl(
    const std::vector<Edge>& edges,
    float min_disp_px);

float compute_adaptive_min_disp_impl(const std::vector<Edge>& edges);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static cv::Mat rand_gray(int H, int W, uint64_t seed = 0) {
    cv::RNG rng(seed);
    cv::Mat m(H, W, CV_8UC1);
    rng.fill(m, cv::RNG::UNIFORM, 0, 256);
    return m;
}

static cv::Mat bright_block_gray(int H, int W, int y0, int x0, int bh, int bw) {
    cv::Mat m = cv::Mat::zeros(H, W, CV_8UC1);
    cv::Rect roi(x0, y0, bw, bh);
    m(roi).setTo(cv::Scalar(200));
    return m;
}

// ---------------------------------------------------------------------------
// phase_correlate_masked tests
// ---------------------------------------------------------------------------

TEST_CASE("phase_correlate_masked: returns result with dx, dy, response", "[matching][not_impl]") {
    cv::Mat a = rand_gray(120, 160, 0);
    cv::Mat b = rand_gray(120, 160, 1);
    REQUIRE_THROWS_AS(
        phase_correlate_masked_impl(a, b, cv::Mat{}, cv::Mat{}),
        std::runtime_error
    );
    // Post-Phase-3:
    // auto r = phase_correlate_masked_impl(a, b, cv::Mat{}, cv::Mat{});
    // CHECK(r.response >= 0.0f); CHECK(r.response <= 1.0f);
}

TEST_CASE("phase_correlate_masked: identical frames give |dx|<1 and |dy|<1", "[matching][not_impl]") {
    cv::Mat a = rand_gray(64, 64, 1);
    REQUIRE_THROWS_AS(
        phase_correlate_masked_impl(a, a.clone(), cv::Mat{}, cv::Mat{}),
        std::runtime_error
    );
    // Post-Phase-3:
    // auto r = phase_correlate_masked_impl(a, a.clone(), cv::Mat{}, cv::Mat{});
    // CHECK(std::abs(r.dx) < 1.0f);
    // CHECK(std::abs(r.dy) < 1.0f);
}

TEST_CASE("phase_correlate_masked: bright block shifted by (10,10) detected within 2px", "[matching][not_impl]") {
    const int H = 128, W = 128;
    cv::Mat a = bright_block_gray(H, W, 20, 20, 60, 60);
    cv::Mat b = bright_block_gray(H, W, 30, 30, 60, 60);  // shifted by (10,10)
    REQUIRE_THROWS_AS(
        phase_correlate_masked_impl(a, b, cv::Mat{}, cv::Mat{}),
        std::runtime_error
    );
    // Post-Phase-3:
    // auto r = phase_correlate_masked_impl(a, b, cv::Mat{}, cv::Mat{});
    // CHECK(std::abs(r.dx - 10.0f) < 2.0f);
    // CHECK(std::abs(r.dy - 10.0f) < 2.0f);
}

TEST_CASE("phase_correlate_masked: response is in [0, 1]", "[matching][not_impl]") {
    cv::Mat a = rand_gray(64, 64, 2);
    cv::Mat b = rand_gray(64, 64, 3);
    REQUIRE_THROWS_AS(
        phase_correlate_masked_impl(a, b, cv::Mat{}, cv::Mat{}),
        std::runtime_error
    );
    // Post-Phase-3:
    // auto r = phase_correlate_masked_impl(a, b, cv::Mat{}, cv::Mat{});
    // CHECK(r.response >= 0.0f); CHECK(r.response <= 1.0f);
}

// ---------------------------------------------------------------------------
// reject_static_edges tests
// ---------------------------------------------------------------------------

TEST_CASE("reject_static_edges: removes edges where both |dx|<min and |dy|<min", "[matching][not_impl]") {
    std::vector<Edge> edges = {
        {0, 1,   0.5f,   0.2f, 0.8f},   // |dx|=0.5 < 50, |dy|=0.2 < 50 → remove
        {1, 2, 100.0f, 100.0f, 0.9f},   // |dx|=100 >= 50 → keep
        {2, 3,  -0.1f,   0.3f, 0.7f},   // both < 50 → remove
    };
    REQUIRE_THROWS_AS(
        reject_static_edges_impl(edges, 50.0f),
        std::runtime_error
    );
    // Post-Phase-3:
    // auto filtered = reject_static_edges_impl(edges, 50.0f);
    // REQUIRE(filtered.size() == 1u);
    // CHECK(filtered[0].i == 1);
}

TEST_CASE("reject_static_edges: edge with large |dx| only is kept", "[matching][not_impl]") {
    // |dx| >= min_disp → keep even if |dy| < min_disp
    std::vector<Edge> edges = {
        {0, 1, 200.0f, 0.0f, 0.9f},
        {1, 2,   0.0f, 200.0f, 0.9f},
    };
    REQUIRE_THROWS_AS(
        reject_static_edges_impl(edges, 50.0f),
        std::runtime_error
    );
    // Post-Phase-3:
    // auto filtered = reject_static_edges_impl(edges, 50.0f);
    // CHECK(filtered.size() == 2u);
}

TEST_CASE("reject_static_edges: empty input returns empty output", "[matching][not_impl]") {
    std::vector<Edge> edges;
    REQUIRE_THROWS_AS(
        reject_static_edges_impl(edges, 50.0f),
        std::runtime_error
    );
    // Post-Phase-3:
    // auto filtered = reject_static_edges_impl(edges, 50.0f);
    // CHECK(filtered.empty());
}

// ---------------------------------------------------------------------------
// compute_adaptive_min_disp tests
// ---------------------------------------------------------------------------

TEST_CASE("compute_adaptive_min_disp: returns positive value", "[matching][not_impl]") {
    std::vector<Edge> edges = {
        {0, 1, 80.0f, 90.0f, 0.9f},
        {1, 2, 70.0f, 100.0f, 0.85f},
    };
    REQUIRE_THROWS_AS(
        compute_adaptive_min_disp_impl(edges),
        std::runtime_error
    );
    // Post-Phase-3:
    // float t = compute_adaptive_min_disp_impl(edges);
    // CHECK(t > 0.0f);
}

TEST_CASE("compute_adaptive_min_disp: larger edge displacements give larger threshold", "[matching][not_impl]") {
    std::vector<Edge> small_edges = {{0, 1, 5.0f, 5.0f, 1.0f}};
    std::vector<Edge> large_edges = {{0, 1, 500.0f, 500.0f, 1.0f}};
    REQUIRE_THROWS_AS(compute_adaptive_min_disp_impl(small_edges), std::runtime_error);
    REQUIRE_THROWS_AS(compute_adaptive_min_disp_impl(large_edges), std::runtime_error);
    // Post-Phase-3:
    // float t_small = compute_adaptive_min_disp_impl(small_edges);
    // float t_large = compute_adaptive_min_disp_impl(large_edges);
    // CHECK(t_large > t_small);
}
