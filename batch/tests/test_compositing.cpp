// ---------------------------------------------------------------------------
// batch/tests/test_compositing.cpp
//
// Native C++ unit tests for batch::compositing functions.
//
// Tests (all pure C++ — no Python references):
//   zone_chroma_align  : output shape/type
//   zone_lum_norm      : output shape/type, identity-zone no-change
//   zone_sat_norm      : output shape/type
//   zone_contrast_eq   : output shape/type
//   zone_hue_eq        : output shape/type
//   laplacian_blend    : output shape/type, horizontal seam continuity
//   single_pose_soft_edge : output shape/type
//   normalize_warped_frames : output count and frame shapes
//
// All tagged [not_impl] until Phase 2; REQUIRE_THROWS_AS guards every call.
// ---------------------------------------------------------------------------

#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>

#include <opencv2/core.hpp>
#include <stdexcept>
#include <vector>

// ---------------------------------------------------------------------------
// Forward declarations of internal impl functions (defined in compositing.cpp)
// ---------------------------------------------------------------------------
cv::Mat zone_chroma_align_impl(const cv::Mat& fa, const cv::Mat& fb, float min_shift_px);
cv::Mat zone_lum_norm_impl    (const cv::Mat& fa, const cv::Mat& fb, float gain_clamp);
cv::Mat zone_sat_norm_impl    (const cv::Mat& fa, const cv::Mat& fb, float gain_clamp);
cv::Mat zone_contrast_eq_impl (const cv::Mat& fa, const cv::Mat& fb, float clamp);
cv::Mat zone_hue_eq_impl      (const cv::Mat& fa, const cv::Mat& fb, float min_hue_diff_deg);

cv::Mat laplacian_blend_impl(
    const cv::Mat& fa, const cv::Mat& fb,
    const std::vector<int>& path,
    int feather_px, int n_bands, float alpha_fine_weight);

cv::Mat single_pose_soft_edge_impl(
    const cv::Mat& fa, const cv::Mat& fb,
    const std::vector<int>& path, int soft_px);

std::vector<cv::Mat> normalize_warped_frames_impl(
    const std::vector<cv::Mat>& frames,
    const std::vector<cv::Mat>& bg_masks,
    int ref_frame_idx,
    bool adaptive_gain_clamp,
    float coherence_limit);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static cv::Mat rand_bgr(int H, int W, uint64_t seed = 0) {
    cv::RNG rng(seed);
    cv::Mat m(H, W, CV_8UC3);
    rng.fill(m, cv::RNG::UNIFORM, 0, 256);
    return m;
}

static cv::Mat solid_bgr(int H, int W, uint8_t v) {
    return cv::Mat(H, W, CV_8UC3, cv::Scalar(v, v, v));
}

static cv::Mat full_mask(int H, int W) {
    return cv::Mat(H, W, CV_8UC1, cv::Scalar(255));
}

static std::vector<int> midline_path(int W, int H) {
    return std::vector<int>(W, H / 2);
}

// ---------------------------------------------------------------------------
// Zone normalization function tests
// ---------------------------------------------------------------------------

// Macro to generate a shape/type test for each zone function
#define ZONE_SHAPE_TEST(fn_name, impl_fn, gain_arg)                             \
TEST_CASE(#fn_name " returns BGR mat of same shape as input", "[compositing][not_impl]") { \
    const int H = 64, W = 80;                                                   \
    cv::Mat fa = rand_bgr(H, W, 0);                                             \
    cv::Mat fb = rand_bgr(H, W, 1);                                             \
    REQUIRE_THROWS_AS(impl_fn(fa, fb, gain_arg), std::runtime_error);          \
    /* Post-Phase-2:                                                             \
    cv::Mat out = impl_fn(fa, fb, gain_arg);                                    \
    REQUIRE(out.rows == H); REQUIRE(out.cols == W);                             \
    REQUIRE(out.type() == CV_8UC3); */                                          \
}

ZONE_SHAPE_TEST(zone_chroma_align, zone_chroma_align_impl, 2.0f)
ZONE_SHAPE_TEST(zone_lum_norm,     zone_lum_norm_impl,     2.0f)
ZONE_SHAPE_TEST(zone_sat_norm,     zone_sat_norm_impl,     2.0f)
ZONE_SHAPE_TEST(zone_contrast_eq,  zone_contrast_eq_impl,  2.0f)
ZONE_SHAPE_TEST(zone_hue_eq,       zone_hue_eq_impl,       5.0f)

TEST_CASE("zone_lum_norm identity: fb==fa returns frame within 2 luma of fa", "[compositing][not_impl]") {
    const int H = 40, W = 50;
    cv::Mat fa = rand_bgr(H, W, 5);
    cv::Mat fb = fa.clone();
    REQUIRE_THROWS_AS(zone_lum_norm_impl(fa, fb, 2.0f), std::runtime_error);
    // Post-Phase-2:
    // cv::Mat out = zone_lum_norm_impl(fa, fb, 2.0f);
    // cv::Mat diff;
    // cv::absdiff(out, fa, diff);
    // double maxVal;
    // cv::minMaxLoc(diff, nullptr, &maxVal);
    // CHECK(maxVal <= 2.0);
}

// ---------------------------------------------------------------------------
// laplacian_blend tests
// ---------------------------------------------------------------------------

TEST_CASE("laplacian_blend returns BGR mat of input shape", "[compositing][not_impl]") {
    const int H = 80, W = 120;
    cv::Mat fa   = rand_bgr(H, W, 0);
    cv::Mat fb   = rand_bgr(H, W, 1);
    auto path    = midline_path(W, H);
    REQUIRE_THROWS_AS(
        laplacian_blend_impl(fa, fb, path, 12, 5, 0.3f),
        std::runtime_error
    );
    // Post-Phase-2:
    // cv::Mat out = laplacian_blend_impl(fa, fb, path, 12, 5, 0.3f);
    // REQUIRE(out.rows == H); REQUIRE(out.cols == W);
    // REQUIRE(out.type() == CV_8UC3);
}

TEST_CASE("laplacian_blend horizontal seam shows no hard edge between adjacent rows", "[compositing][not_impl]") {
    // Black top / white bottom, midline seam: adjacent rows near seam must
    // differ by < 200 (blended, not hard-cut).
    const int H = 80, W = 120;
    cv::Mat fa = solid_bgr(H, W, 0);    // black
    cv::Mat fb = solid_bgr(H, W, 255);  // white
    auto path  = midline_path(W, H);
    REQUIRE_THROWS_AS(
        laplacian_blend_impl(fa, fb, path, 20, 5, 0.3f),
        std::runtime_error
    );
    // Post-Phase-2:
    // cv::Mat out = laplacian_blend_impl(fa, fb, path, 20, 5, 0.3f);
    // int mid = H / 2;
    // for (int x = 0; x < W; ++x) {
    //     int above = out.at<cv::Vec3b>(mid - 1, x)[0];
    //     int below = out.at<cv::Vec3b>(mid + 1, x)[0];
    //     CHECK(std::abs(below - above) < 200);
    // }
}

// ---------------------------------------------------------------------------
// single_pose_soft_edge tests
// ---------------------------------------------------------------------------

TEST_CASE("single_pose_soft_edge returns BGR mat of input shape", "[compositing][not_impl]") {
    const int H = 60, W = 80;
    cv::Mat fa = rand_bgr(H, W, 0);
    cv::Mat fb = rand_bgr(H, W, 1);
    auto path  = midline_path(W, H);
    REQUIRE_THROWS_AS(
        single_pose_soft_edge_impl(fa, fb, path, 6),
        std::runtime_error
    );
}

// ---------------------------------------------------------------------------
// normalize_warped_frames tests
// ---------------------------------------------------------------------------

TEST_CASE("normalize_warped_frames returns N frames of correct shape", "[compositing][not_impl]") {
    const int N = 5, H = 60, W = 80;
    std::vector<cv::Mat> frames, masks;
    cv::RNG rng(0);
    for (int i = 0; i < N; ++i) {
        cv::Mat f(H, W, CV_8UC3);
        rng.fill(f, cv::RNG::UNIFORM, 0, 256);
        frames.push_back(f);
        masks.push_back(cv::Mat(H, W, CV_8UC1, cv::Scalar(255)));
    }
    REQUIRE_THROWS_AS(
        normalize_warped_frames_impl(frames, masks, 0, true, 20.0f),
        std::runtime_error
    );
    // Post-Phase-2:
    // auto result = normalize_warped_frames_impl(frames, masks, 0, true, 20.0f);
    // REQUIRE(static_cast<int>(result.size()) == N);
    // for (auto& r : result) { REQUIRE(r.rows == H); REQUIRE(r.cols == W); }
}
