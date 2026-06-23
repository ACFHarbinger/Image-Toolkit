// ---------------------------------------------------------------------------
// batch/tests/test_wave_correct.cpp
//
// Native C++ unit tests for batch::wave_correct functions.
//
// Tests:
//   wave_correct_values_impl : removes linear drift, anchors at first value,
//                              skips correction when range < threshold,
//                              skips for N < 3, handles zero-slope input
// ---------------------------------------------------------------------------

#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>

#include <algorithm>
#include <cmath>
#include <numeric>
#include <vector>

// ---------------------------------------------------------------------------
// Forward declaration of impl function (wave_correct.cpp)
// ---------------------------------------------------------------------------
std::vector<float> wave_correct_values_impl(
    const std::vector<float>& vals,
    float min_range_px);

// ---------------------------------------------------------------------------
// wave_correct_values_impl tests
// ---------------------------------------------------------------------------

TEST_CASE("wave_correct: N < 3 returns input unchanged", "[wave_correct]") {
    std::vector<float> vals = {10.0f, 20.0f};
    auto result = wave_correct_values_impl(vals, 5.0f);
    REQUIRE(result.size() == 2u);
    CHECK(result[0] == Catch::Approx(10.0f));
    CHECK(result[1] == Catch::Approx(20.0f));
}

TEST_CASE("wave_correct: range below threshold returns input unchanged", "[wave_correct]") {
    // ptp = 3.0 < min_range_px = 5.0 → no correction
    std::vector<float> vals = {1.0f, 2.0f, 4.0f};
    auto result = wave_correct_values_impl(vals, 5.0f);
    REQUIRE(result.size() == 3u);
    CHECK(result[0] == Catch::Approx(1.0f));
    CHECK(result[1] == Catch::Approx(2.0f));
    CHECK(result[2] == Catch::Approx(4.0f));
}

TEST_CASE("wave_correct: pure linear drift is fully removed", "[wave_correct]") {
    // vals[i] = 5*i + 10 (purely linear, slope=5, intercept=10)
    // After correction: all corrected values should equal vals[0]=10 (flat)
    std::vector<float> vals = {10.0f, 15.0f, 20.0f, 25.0f, 30.0f};
    auto result = wave_correct_values_impl(vals, 5.0f);
    REQUIRE(result.size() == 5u);
    for (float v : result)
        CHECK(v == Catch::Approx(vals[0]).epsilon(1e-4f));
}

TEST_CASE("wave_correct: result is anchored at vals[0]", "[wave_correct]") {
    // After correction the first value must equal original vals[0]
    std::vector<float> vals = {7.0f, 13.0f, 15.0f, 25.0f, 35.0f};
    auto result = wave_correct_values_impl(vals, 5.0f);
    REQUIRE(!result.empty());
    CHECK(result[0] == Catch::Approx(vals[0]).epsilon(1e-3f));
}

TEST_CASE("wave_correct: already flat sequence (zero slope) unchanged", "[wave_correct]") {
    // All values identical → range=0 < threshold → returned as-is
    std::vector<float> vals = {5.0f, 5.0f, 5.0f, 5.0f};
    auto result = wave_correct_values_impl(vals, 5.0f);
    for (size_t i = 0; i < result.size(); ++i)
        CHECK(result[i] == Catch::Approx(vals[i]));
}

TEST_CASE("wave_correct: output has same length as input", "[wave_correct]") {
    std::vector<float> vals(20);
    for (int i = 0; i < 20; ++i) vals[i] = i * 2.0f + std::sin(i * 0.5f);
    auto result = wave_correct_values_impl(vals, 5.0f);
    CHECK(result.size() == vals.size());
}

TEST_CASE("wave_correct: removes linear component of mixed signal", "[wave_correct]") {
    // vals = linear_trend + sinusoidal noise
    // After correction, linear trend should be gone; residuals should be
    // much smaller than the original range.
    int N = 20;
    float slope = 10.0f, intercept = 5.0f;
    std::vector<float> vals(N);
    for (int i = 0; i < N; ++i)
        vals[i] = slope * i + intercept + 2.0f * std::sin(i * 0.8f);

    auto result = wave_correct_values_impl(vals, 5.0f);

    // Compute range of corrected values — should be much smaller than original
    float orig_range = *std::max_element(vals.begin(), vals.end())
                     - *std::min_element(vals.begin(), vals.end());
    float corr_range = *std::max_element(result.begin(), result.end())
                     - *std::min_element(result.begin(), result.end());

    // Corrected range should be substantially reduced (just the sinusoidal part)
    CHECK(corr_range < orig_range * 0.15f);
}
