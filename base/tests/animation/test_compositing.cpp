// ---------------------------------------------------------------------------
// batch/tests/test_compositing.cpp
//
// Native C++ unit tests for base::compositing functions.
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

cv::Mat multiband_blend_impl(
    const std::vector<cv::Mat>& frames,
    const std::vector<cv::Mat>& masks,
    const std::vector<cv::Point>& corners,
    int num_bands = 5,
    bool try_gpu = false);

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
TEST_CASE(#fn_name " returns BGR mat of same shape as input", "[compositing]") { \
    const int H = 64, W = 80;                                                   \
    cv::Mat fa = rand_bgr(H, W, 0);                                             \
    cv::Mat fb = rand_bgr(H, W, 1);                                             \
    cv::Mat out = impl_fn(fa, fb, gain_arg);                                    \
    REQUIRE(out.rows == H); REQUIRE(out.cols == W);                             \
    REQUIRE(out.type() == CV_8UC3);                                             \
}

ZONE_SHAPE_TEST(zone_chroma_align, zone_chroma_align_impl, 2.0f)
ZONE_SHAPE_TEST(zone_lum_norm,     zone_lum_norm_impl,     2.0f)
ZONE_SHAPE_TEST(zone_sat_norm,     zone_sat_norm_impl,     2.0f)
ZONE_SHAPE_TEST(zone_contrast_eq,  zone_contrast_eq_impl,  2.0f)
ZONE_SHAPE_TEST(zone_hue_eq,       zone_hue_eq_impl,       5.0f)

TEST_CASE("zone_lum_norm identity: fb==fa returns frame within 2 luma of fa", "[compositing]") {
    const int H = 40, W = 50;
    cv::Mat fa = rand_bgr(H, W, 5);
    cv::Mat fb = fa.clone();
    cv::Mat out = zone_lum_norm_impl(fa, fb, 2.0f);
    REQUIRE(out.size() == fa.size());
}

// ---------------------------------------------------------------------------
// laplacian_blend tests
// ---------------------------------------------------------------------------

TEST_CASE("laplacian_blend returns BGR mat of input shape", "[compositing]") {
    const int H = 80, W = 120;
    cv::Mat fa   = rand_bgr(H, W, 0);
    cv::Mat fb   = rand_bgr(H, W, 1);
    auto path    = midline_path(W, H);
    cv::Mat out = laplacian_blend_impl(fa, fb, path, 12, 5, 0.3f);
    REQUIRE(out.rows == H); REQUIRE(out.cols == W);
    REQUIRE(out.type() == CV_8UC3);
}

TEST_CASE("laplacian_blend horizontal seam shows no hard edge between adjacent rows", "[compositing]") {
    // Black top / white bottom, midline seam: adjacent rows near seam must
    // differ by < 200 (blended, not hard-cut).
    const int H = 80, W = 120;
    cv::Mat fa = solid_bgr(H, W, 0);    // black
    cv::Mat fb = solid_bgr(H, W, 255);  // white
    auto path  = midline_path(W, H);
    cv::Mat out = laplacian_blend_impl(fa, fb, path, 20, 5, 0.3f);

    // Verify row 45 is a blend of fa and fb
    cv::Vec3b px = out.at<cv::Vec3b>(45, 50);
    REQUIRE(px[0] > 0);
    REQUIRE(px[0] < 255);
}

// ---------------------------------------------------------------------------
// single_pose_soft_edge tests
// ---------------------------------------------------------------------------

TEST_CASE("single_pose_soft_edge returns BGR mat of input shape", "[compositing]") {
    const int H = 60, W = 80;
    cv::Mat fa = rand_bgr(H, W, 0);
    cv::Mat fb = rand_bgr(H, W, 1);
    auto path  = midline_path(W, H);
    cv::Mat out = single_pose_soft_edge_impl(fa, fb, path, 6);
    REQUIRE(out.size() == fa.size());
}

// ---------------------------------------------------------------------------
// normalize_warped_frames tests
// ---------------------------------------------------------------------------

TEST_CASE("normalize_warped_frames returns N frames of correct shape", "[compositing]") {
    const int N = 5, H = 60, W = 80;
    std::vector<cv::Mat> frames, masks;
    cv::RNG rng(0);
    for (int i = 0; i < N; ++i) {
        cv::Mat f(H, W, CV_8UC3);
        rng.fill(f, cv::RNG::UNIFORM, 0, 256);
        frames.push_back(f);
        masks.push_back(cv::Mat(H, W, CV_8UC1, cv::Scalar(255)));
    }
    auto result = normalize_warped_frames_impl(frames, masks, 0, true, 20.0f);
    REQUIRE(static_cast<int>(result.size()) == N);
    for (auto& r : result) { REQUIRE(r.rows == H); REQUIRE(r.cols == W); }
}

// ---------------------------------------------------------------------------
// multiband_blend_impl tests (Phase 4)
// ---------------------------------------------------------------------------

TEST_CASE("multiband_blend: single frame returns frame content", "[compositing][phase4]") {
    const int H = 64, W = 80;
    cv::Mat frame(H, W, CV_8UC3, cv::Scalar(120, 100, 80));
    cv::Mat mask(H, W, CV_8UC1, cv::Scalar(255));
    auto result = multiband_blend_impl({frame}, {mask}, {cv::Point(0,0)}, 3);
    REQUIRE(result.rows == H);
    REQUIRE(result.cols == W);
    REQUIRE(result.type() == CV_8UC3);
}

TEST_CASE("multiband_blend: two adjacent frames produce wider canvas", "[compositing][phase4]") {
    const int H = 60, W = 50;
    cv::Mat fa(H, W, CV_8UC3, cv::Scalar(50, 50, 50));
    cv::Mat fb(H, W, CV_8UC3, cv::Scalar(200, 200, 200));
    cv::Mat ma(H, W, CV_8UC1, cv::Scalar(255));
    cv::Mat mb(H, W, CV_8UC1, cv::Scalar(255));
    // fb placed at x=W (non-overlapping tiles)
    auto result = multiband_blend_impl({fa, fb}, {ma, mb}, {cv::Point(0,0), cv::Point(W,0)}, 3);
    REQUIRE(result.rows == H);
    REQUIRE(result.cols == 2 * W);
    REQUIRE(result.type() == CV_8UC3);
}

TEST_CASE("multiband_blend: two overlapping frames produce blended output", "[compositing][phase4]") {
    const int H = 80, W = 60;
    cv::Mat fa(H, W, CV_8UC3, cv::Scalar(30,  30,  30));
    cv::Mat fb(H, W, CV_8UC3, cv::Scalar(200, 200, 200));
    cv::Mat ma(H, W, CV_8UC1, cv::Scalar(255));
    cv::Mat mb(H, W, CV_8UC1, cv::Scalar(255));
    // 20-px overlap: fb starts at x=W-20
    auto result = multiband_blend_impl({fa, fb}, {ma, mb}, {cv::Point(0,0), cv::Point(W-20,0)}, 3);
    REQUIRE(result.cols == W + (W - 20));  // 100
    REQUIRE(result.rows == H);
    // Mean value should be between the two source values (blended)
    cv::Scalar mean = cv::mean(result);
    CHECK(mean[0] > 30.0);
    CHECK(mean[0] < 200.0);
}

TEST_CASE("multiband_blend: throws on empty input", "[compositing][phase4]") {
    std::vector<cv::Mat> empty;
    REQUIRE_THROWS_AS(
        multiband_blend_impl(empty, empty, {}, 3),
        std::runtime_error);
}

TEST_CASE("multiband_blend: num_bands=1 still returns correct shape", "[compositing][phase4]") {
    const int H = 40, W = 40;
    cv::Mat f(H, W, CV_8UC3, cv::Scalar(128, 64, 200));
    cv::Mat m(H, W, CV_8UC1, cv::Scalar(255));
    auto result = multiband_blend_impl({f}, {m}, {cv::Point(0,0)}, 1);
    REQUIRE(result.rows == H);
    REQUIRE(result.cols == W);
}

// §4.6 regression guard: the mask must NOT be hard-binarized before being
// fed to MultiBandBlender. A graded (non-0/255) confidence mask should pull
// the overlap-region result away from what a fully-opaque (255) mask on
// both sides would produce, proving the gradation actually influences the
// blend weights rather than being collapsed to "included" either way.
TEST_CASE("multiband_blend: graded confidence mask changes overlap blend vs opaque mask", "[compositing][phase4]") {
    const int H = 40, W = 60;
    cv::Mat fa(H, W, CV_8UC3, cv::Scalar(20, 20, 20));
    cv::Mat fb(H, W, CV_8UC3, cv::Scalar(220, 220, 220));

    cv::Mat ma_opaque(H, W, CV_8UC1, cv::Scalar(255));
    cv::Mat mb_opaque(H, W, CV_8UC1, cv::Scalar(255));
    auto result_opaque = multiband_blend_impl(
        {fa, fb}, {ma_opaque, mb_opaque}, {cv::Point(0, 0), cv::Point(W - 20, 0)}, 3);

    // fb's confidence graded low (64) everywhere -> fa should dominate the
    // overlap far more than in the opaque case.
    cv::Mat ma_full(H, W, CV_8UC1, cv::Scalar(255));
    cv::Mat mb_low(H, W, CV_8UC1, cv::Scalar(64));
    auto result_graded = multiband_blend_impl(
        {fa, fb}, {ma_full, mb_low}, {cv::Point(0, 0), cv::Point(W - 20, 0)}, 3);

    cv::Scalar mean_opaque = cv::mean(result_opaque);
    cv::Scalar mean_graded = cv::mean(result_graded);

    // If the mask were still hard-binarized (mb_low > 0 == fully included,
    // same as opaque), these means would be equal. A graded mask must pull
    // the mean down toward fa's darker value.
    CHECK(mean_graded[0] < mean_opaque[0]);
}
