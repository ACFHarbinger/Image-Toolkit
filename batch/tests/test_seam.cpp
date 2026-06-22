// ---------------------------------------------------------------------------
// batch/tests/test_seam.cpp
//
// Native C++ unit tests for batch::seam functions.
//
// Tests (all pure C++ — no Python references required):
//   seam_cut  : output length, row range, semantic cost, transition penalty,
//               single-column edge case, waypoint pinning
//   build_seam_cost_map : output shape, dtype equivalent, all-background = 0
//   seam_batch : count and per-path length
//
// NOTE: all tests call BATCH_NOT_IMPLEMENTED stubs and are therefore tagged
// [not_impl] so they can be excluded until Phase 2 lands:
//   ./batch_tests "[seam]" --allow-running-no-tests
// ---------------------------------------------------------------------------

#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>
#include <catch2/matchers/catch_matchers_vector.hpp>

#include <opencv2/core.hpp>
#include <stdexcept>
#include <vector>

// Pull in internal seam helpers.  The real implementations are compiled via
// batch_impl; until Phase 2 they throw std::runtime_error("not implemented").
// Forward-declare the C-linkage entry points used by pybind11 so we can call
// the underlying implementations directly without going through Python.
//
// Strategy: each src/seam.cpp function is separated into a *_impl free
// function.  The pybind11 wrapper calls the impl; tests call the impl too.
// Until Phase 2 the impl == BATCH_NOT_IMPLEMENTED, so all tests below are
// wrapped in REQUIRE_THROWS_AS(…, std::runtime_error) and tagged [not_impl].
// When Phase 2 ships, remove the throws wrappers and the [not_impl] tag.

// ---------------------------------------------------------------------------
// Helpers: build cv::Mat test data without Python
// ---------------------------------------------------------------------------

static cv::Mat random_bgr(int H, int W, uint64_t seed = 0) {
    cv::RNG rng(seed);
    cv::Mat m(H, W, CV_8UC3);
    rng.fill(m, cv::RNG::UNIFORM, 0, 256);
    return m;
}

static cv::Mat zeros_mask(int H, int W) {
    return cv::Mat::zeros(H, W, CV_8UC1);
}

static cv::Mat ones_mask(int H, int W) {
    return cv::Mat(H, W, CV_8UC1, cv::Scalar(255));
}

static cv::Mat random_cost(int H, int W, uint64_t seed = 42) {
    cv::RNG rng(seed);
    cv::Mat m(H, W, CV_32F);
    rng.fill(m, cv::RNG::UNIFORM, 0.0f, 1.0f);
    return m;
}

// ---------------------------------------------------------------------------
// Forward declarations of internal impl functions.
// These will be defined in seam.cpp once Phase 2 is implemented.
// ---------------------------------------------------------------------------
std::vector<int> seam_cut_impl(
    const cv::Mat& fa_zone,
    const cv::Mat& fb_zone,
    const cv::Mat& sem_cost,       // may be empty
    const std::vector<int>& waypoints,
    float transition_penalty,
    float edge_weight);

cv::Mat build_seam_cost_map_impl(
    const cv::Mat& fa_zone,
    const cv::Mat& bg_mask_a,
    const cv::Mat& bg_mask_b,
    float cost_map_blur_sigma,
    float cost_col_smooth_sigma,
    bool  cost_map_norm,
    float scatter_cost_weight,
    const std::vector<int>& pinned_rows);

std::vector<std::vector<int>> seam_batch_impl(
    const std::vector<std::pair<cv::Mat,cv::Mat>>& zone_pairs,
    float edge_weight,
    float transition_penalty);

// ---------------------------------------------------------------------------
// seam_cut tests
// ---------------------------------------------------------------------------

TEST_CASE("seam_cut returns path of length W", "[seam][not_impl]") {
    const int H = 40, W = 60;
    cv::Mat fa = random_bgr(H, W, 0);
    cv::Mat fb = random_bgr(H, W, 1);
    REQUIRE_THROWS_AS(
        seam_cut_impl(fa, fb, cv::Mat{}, {}, 0.0f, 1.0f),
        std::runtime_error
    );
    // Post-Phase-2: uncomment and remove REQUIRE_THROWS_AS wrapper
    // auto path = seam_cut_impl(fa, fb, cv::Mat{}, {}, 0.0f, 1.0f);
    // REQUIRE(static_cast<int>(path.size()) == W);
}

TEST_CASE("seam_cut path rows are in [0, H)", "[seam][not_impl]") {
    const int H = 40, W = 60;
    cv::Mat fa = random_bgr(H, W, 2);
    cv::Mat fb = random_bgr(H, W, 3);
    REQUIRE_THROWS_AS(
        seam_cut_impl(fa, fb, cv::Mat{}, {}, 0.0f, 1.0f),
        std::runtime_error
    );
    // Post-Phase-2:
    // auto path = seam_cut_impl(fa, fb, cv::Mat{}, {}, 0.0f, 1.0f);
    // for (int y : path) { CHECK(y >= 0); CHECK(y < H); }
}

TEST_CASE("seam_cut accepts optional semantic cost map", "[seam][not_impl]") {
    const int H = 30, W = 50;
    cv::Mat fa = random_bgr(H, W, 4);
    cv::Mat fb = random_bgr(H, W, 5);
    cv::Mat sem = random_cost(H, W, 42);
    REQUIRE_THROWS_AS(
        seam_cut_impl(fa, fb, sem, {}, 0.0f, 1.0f),
        std::runtime_error
    );
}

TEST_CASE("seam_cut with high transition_penalty biases path toward midline", "[seam][not_impl]") {
    // With high penalty, mean |path[x] - H/2| should be <= mean without penalty.
    // Both calls are expected to throw in Phase 1; test documents the contract.
    const int H = 40, W = 60;
    cv::Mat fa = random_bgr(H, W, 7);
    cv::Mat fb = random_bgr(H, W, 8);
    REQUIRE_THROWS_AS(
        seam_cut_impl(fa, fb, cv::Mat{}, {}, 0.0f, 1.0f),
        std::runtime_error
    );
    REQUIRE_THROWS_AS(
        seam_cut_impl(fa, fb, cv::Mat{}, {}, 5.0f, 1.0f),
        std::runtime_error
    );
    // Post-Phase-2:
    // auto path_no_pen = seam_cut_impl(fa, fb, cv::Mat{}, {}, 0.0f, 1.0f);
    // auto path_pen    = seam_cut_impl(fa, fb, cv::Mat{}, {}, 5.0f, 1.0f);
    // double mid = H / 2.0;
    // auto mean_dist = [&](const std::vector<int>& p) {
    //     double s = 0; for (int y : p) s += std::abs(y - mid); return s / p.size();
    // };
    // CHECK(mean_dist(path_pen) <= mean_dist(path_no_pen));
}

TEST_CASE("seam_cut handles single-column zone (W=1)", "[seam][not_impl]") {
    const int H = 20, W = 1;
    cv::Mat fa = random_bgr(H, W, 9);
    cv::Mat fb = random_bgr(H, W, 10);
    REQUIRE_THROWS_AS(
        seam_cut_impl(fa, fb, cv::Mat{}, {}, 0.0f, 1.0f),
        std::runtime_error
    );
    // Post-Phase-2:
    // auto path = seam_cut_impl(fa, fb, cv::Mat{}, {}, 0.0f, 1.0f);
    // REQUIRE(path.size() == 1u);
    // CHECK(path[0] >= 0); CHECK(path[0] < H);
}

// ---------------------------------------------------------------------------
// build_seam_cost_map tests
// ---------------------------------------------------------------------------

TEST_CASE("build_seam_cost_map returns float32 mat of shape (H,W)", "[seam][not_impl]") {
    const int H = 50, W = 80;
    cv::Mat fa     = random_bgr(H, W, 0);
    cv::Mat mask_a = ones_mask(H, W);
    cv::Mat mask_b = ones_mask(H, W);
    REQUIRE_THROWS_AS(
        build_seam_cost_map_impl(fa, mask_a, mask_b, 0.0f, 0.0f, true, 0.0f, {}),
        std::runtime_error
    );
    // Post-Phase-2:
    // cv::Mat cost = build_seam_cost_map_impl(fa, mask_a, mask_b, 0.0f, 0.0f, true, 0.0f, {});
    // REQUIRE(cost.rows == H);
    // REQUIRE(cost.cols == W);
    // REQUIRE(cost.type() == CV_32F);
}

TEST_CASE("build_seam_cost_map all-background gives near-zero cost", "[seam][not_impl]") {
    const int H = 30, W = 40;
    cv::Mat fa     = cv::Mat::zeros(H, W, CV_8UC3);
    cv::Mat mask_a = zeros_mask(H, W);
    cv::Mat mask_b = zeros_mask(H, W);
    REQUIRE_THROWS_AS(
        build_seam_cost_map_impl(fa, mask_a, mask_b, 0.0f, 0.0f, true, 0.0f, {}),
        std::runtime_error
    );
    // Post-Phase-2:
    // cv::Mat cost = build_seam_cost_map_impl(fa, mask_a, mask_b, 0.0f, 0.0f, true, 0.0f, {});
    // double mn, mx;
    // cv::minMaxLoc(cost, &mn, &mx);
    // CHECK(mx < 0.5);
}

// ---------------------------------------------------------------------------
// seam_batch tests
// ---------------------------------------------------------------------------

TEST_CASE("seam_batch returns N paths for N zone pairs", "[seam][not_impl]") {
    const int N = 5, H = 30, W = 50;
    std::vector<std::pair<cv::Mat,cv::Mat>> pairs;
    for (int k = 0; k < N; ++k)
        pairs.push_back({random_bgr(H, W, k), random_bgr(H, W, k + 100)});
    REQUIRE_THROWS_AS(
        seam_batch_impl(pairs, 1.0f, 0.0f),
        std::runtime_error
    );
    // Post-Phase-2:
    // auto paths = seam_batch_impl(pairs, 1.0f, 0.0f);
    // REQUIRE(static_cast<int>(paths.size()) == N);
    // for (auto& p : paths) REQUIRE(static_cast<int>(p.size()) == W);
}
