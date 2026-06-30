// ---------------------------------------------------------------------------
// batch/tests/test_exposure.cpp
//
// Native C++ unit tests for base::exposure functions.
//
// Tests (pure C++ — no Python dependencies):
//   blocks_gain_compensate     : output count and shape
//   blocks_channels_compensate : output count and shape
//   correct_vignetting         : identity map, zero map, overflow clamp
//
// Tagged [not_impl]; REQUIRE_THROWS_AS until Phase 2.
// ---------------------------------------------------------------------------

#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>

#include <opencv2/core.hpp>
#include <stdexcept>
#include <vector>

// ---------------------------------------------------------------------------
// Forward declarations of impl functions (exposure.cpp)
// ---------------------------------------------------------------------------
std::vector<cv::Mat> blocks_gain_compensate_impl(
    const std::vector<cv::Mat>& frames,
    const std::vector<cv::Mat>& masks,
    const std::vector<cv::Point2i>& corners,
    int bl_width, int bl_height,
    int nr_feeds, int nr_iterations);

std::vector<cv::Mat> blocks_channels_compensate_impl(
    const std::vector<cv::Mat>& frames,
    const std::vector<cv::Mat>& masks,
    const std::vector<cv::Point2i>& corners,
    int bl_width, int bl_height);

cv::Mat correct_vignetting_impl(
    const cv::Mat& frame,
    const cv::Mat& vignette_map);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static cv::Mat rand_bgr(int H, int W, uint64_t seed = 0) {
    cv::RNG rng(seed);
    cv::Mat m(H, W, CV_8UC3);
    rng.fill(m, cv::RNG::UNIFORM, 0, 256);
    return m;
}

static cv::Mat full_mask(int H, int W) {
    return cv::Mat(H, W, CV_8UC1, cv::Scalar(255));
}

static cv::Mat solid_f32(int H, int W, float v) {
    return cv::Mat(H, W, CV_32F, cv::Scalar(v));
}

// ---------------------------------------------------------------------------
// blocks_gain_compensate tests
// ---------------------------------------------------------------------------

TEST_CASE("blocks_gain_compensate returns N frames of correct shape", "[exposure][not_impl]") {
    auto _test_fn = [&]() {
    const int N = 4, H = 200, W = 300;
    std::vector<cv::Mat>     frames, masks;
    std::vector<cv::Point2i> corners;
    for (int i = 0; i < N; ++i) {
        frames.push_back(rand_bgr(H, W, i));
        masks.push_back(full_mask(H, W));
        corners.push_back({i * 50, 0});
    }
    auto result = blocks_gain_compensate_impl(frames, masks, corners, 32, 32, 1, 2);
    REQUIRE(static_cast<int>(result.size()) == N);
    for (auto& r : result) { REQUIRE(r.rows == H); REQUIRE(r.cols == W); }
    };
    REQUIRE_THROWS_AS(_test_fn(), std::runtime_error);
}

TEST_CASE("blocks_gain_compensate: uniform frames returned unchanged (within 2)", "[exposure][not_impl]") {
    auto _test_fn = [&]() {
    const int N = 3, H = 100, W = 150;
    std::vector<cv::Mat>     frames, masks;
    std::vector<cv::Point2i> corners;
    for (int i = 0; i < N; ++i) {
        frames.push_back(cv::Mat(H, W, CV_8UC3, cv::Scalar(128, 128, 128)));
        masks.push_back(full_mask(H, W));
        corners.push_back({0, 0});
    }
    auto result = blocks_gain_compensate_impl(frames, masks, corners, 32, 32, 1, 2);
    for (int i = 0; i < N; ++i) {
        cv::Mat diff; cv::absdiff(frames[i], result[i], diff);
        double maxVal; cv::minMaxLoc(diff, nullptr, &maxVal);
        CHECK(maxVal <= 2.0);
    }
    };
    REQUIRE_THROWS_AS(_test_fn(), std::runtime_error);
}

// ---------------------------------------------------------------------------
// blocks_channels_compensate tests
// ---------------------------------------------------------------------------

TEST_CASE("blocks_channels_compensate returns N frames of correct shape", "[exposure][not_impl]") {
    auto _test_fn = [&]() {
    const int N = 3, H = 120, W = 160;
    std::vector<cv::Mat>     frames, masks;
    std::vector<cv::Point2i> corners;
    for (int i = 0; i < N; ++i) {
        frames.push_back(rand_bgr(H, W, i));
        masks.push_back(full_mask(H, W));
        corners.push_back({i * 20, 0});
    }
    auto result = blocks_channels_compensate_impl(frames, masks, corners, 32, 32);
    REQUIRE(static_cast<int>(result.size()) == N);
    for (auto& r : result) { REQUIRE(r.rows == H); REQUIRE(r.cols == W); }
    };
    REQUIRE_THROWS_AS(_test_fn(), std::runtime_error);
}

// ---------------------------------------------------------------------------
// correct_vignetting tests
// ---------------------------------------------------------------------------

TEST_CASE("correct_vignetting: identity map (1.0) leaves frame unchanged within 1", "[exposure][not_impl]") {
    auto _test_fn = [&]() {
    const int H = 80, W = 100;
    cv::Mat frame = rand_bgr(H, W, 0);
    cv::Mat vign  = solid_f32(H, W, 1.0f);
    cv::Mat out = correct_vignetting_impl(frame, vign);
    cv::Mat diff; cv::absdiff(out, frame, diff);
    double maxVal; cv::minMaxLoc(diff, nullptr, &maxVal);
    CHECK(maxVal <= 1.0);
    };
    REQUIRE_THROWS_AS(_test_fn(), std::runtime_error);
}

TEST_CASE("correct_vignetting: zero map produces all-black output", "[exposure][not_impl]") {
    auto _test_fn = [&]() {
    const int H = 60, W = 80;
    cv::Mat frame = rand_bgr(H, W, 1);
    // Set values in [50,200] so zero-multiply produces visible change
    frame.setTo(cv::Scalar(100, 100, 100));
    cv::Mat vign = solid_f32(H, W, 0.0f);
    cv::Mat out = correct_vignetting_impl(frame, vign);
    double maxVal; cv::minMaxLoc(out, nullptr, &maxVal);
    CHECK(maxVal == Catch::Approx(0.0).margin(0));
    };
    REQUIRE_THROWS_AS(_test_fn(), std::runtime_error);
}

TEST_CASE("correct_vignetting: values above 255 are clipped to 255", "[exposure][not_impl]") {
    auto _test_fn = [&]() {
    const int H = 40, W = 60;
    cv::Mat frame = cv::Mat(H, W, CV_8UC3, cv::Scalar(200, 200, 200));
    cv::Mat vign  = solid_f32(H, W, 2.0f);  // 200 × 2 = 400 > 255
    cv::Mat out = correct_vignetting_impl(frame, vign);
    double maxVal; cv::minMaxLoc(out, nullptr, &maxVal);
    CHECK(maxVal <= 255.0);
    };
    REQUIRE_THROWS_AS(_test_fn(), std::runtime_error);
}
