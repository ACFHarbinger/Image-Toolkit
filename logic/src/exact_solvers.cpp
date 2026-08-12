/// @file exact_solvers.cpp
/// @brief Exact numerical solvers: DP seam routing, GNC-TLS layer alignment,
///        and convex color harmonization.

#include "exact_solvers.hpp"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <limits>
#include <numeric>

// Opt-in SIMD fast path for solve_seam's DP row fill (see HIE_ENABLE_SIMD_SEAM
// in CMakeLists.txt). Off by default: the scalar path below is unconditionally
// correct and portable, and vectorization here is strictly a performance
// optimization for high-resolution (4K/8K) grids, not an algorithm change --
// logic/test/test_solvers.cpp's SIMD-vs-scalar comparison (built only when
// this is enabled) asserts bit-for-bit identical output.
#if defined(HIE_ENABLE_SIMD_SEAM) && (defined(__x86_64__) || defined(_M_X64) || defined(__i386__)) && defined(__AVX2__)
#define HIE_SIMD_SEAM_AVX2 1
#include <immintrin.h>
#elif defined(HIE_ENABLE_SIMD_SEAM) && (defined(__ARM_NEON) || defined(__aarch64__))
// NOTE: implemented by reasoning from ARM NEON intrinsic semantics, not
// empirically verified on ARM hardware (this development environment is
// x86_64-only) -- worth a real run on AArch64 before relying on it.
#define HIE_SIMD_SEAM_NEON 1
#include <arm_neon.h>
#endif

namespace hybrid_image_editor {

// ─── DP Seam Routing ─────────────────────────────────────────────────────────

SeamResult solve_seam(const std::vector<SeamPixel>& energy_grid,
                      std::size_t rows,
                      std::size_t cols) {
    SeamResult result;
    result.success = false;

    if (energy_grid.size() != rows * cols || rows == 0 || cols == 0) {
        result.error = "Invalid energy grid dimensions";
        return result;
    }

    // Masked pixels carry an effectively infinite cost to protect character regions.
    constexpr float kMaskCost = 1e9f;

    // dp[r][c] = minimum cumulative energy to reach (r, c) from row 0.
    std::vector<float> dp(rows * cols);
    std::vector<int>   parent(rows * cols, -1);

    // Initialize first row
    for (std::size_t c = 0; c < cols; ++c) {
        const auto& px = energy_grid[c];
        dp[c] = px.masked ? kMaskCost : px.energy;
    }

    // Fill DP table row by row. Each row depends only on the previous row
    // (already fully computed), so columns within a row are independent of
    // one another -- safe to vectorize across the column dimension.
    for (std::size_t r = 1; r < rows; ++r) {
        const float* prev_row = &dp[(r - 1) * cols];
        float* cur_row = &dp[r * cols];
        int* cur_parent = &parent[r * cols];
        const SeamPixel* row_px = &energy_grid[r * cols];

        // Exact copy of the original (pre-SIMD) per-cell logic, factored into
        // a lambda so the boundary columns and any non-vectorized remainder
        // always go through the identical, already-tested scalar path.
        auto scalar_cell = [&](std::size_t c) {
            float best = std::numeric_limits<float>::infinity();
            int   best_c = static_cast<int>(c);
            for (int dc = -1; dc <= 1; ++dc) {
                int pc = static_cast<int>(c) + dc;
                if (pc < 0 || pc >= static_cast<int>(cols)) continue;
                float prev = prev_row[pc];
                if (prev < best) {
                    best   = prev;
                    best_c = pc;
                }
            }
            const SeamPixel& px = row_px[c];
            float cost = px.masked ? kMaskCost : px.energy;
            cur_row[c] = best + cost;
            cur_parent[c] = best_c;
        };

        std::size_t c = 0;
        scalar_cell(0);  // left boundary: no c-1 neighbor, always scalar
        c = 1;
        const std::size_t interior_end = cols - 1;  // exclusive; last col handled below

#if defined(HIE_SIMD_SEAM_AVX2)
        const std::size_t simd_end =
            c + (interior_end > c ? ((interior_end - c) / 8) * 8 : 0);
        for (; c < simd_end; c += 8) {
            alignas(32) float cost_block[8];
            for (int k = 0; k < 8; ++k) {
                const SeamPixel& px = row_px[c + k];
                cost_block[k] = px.masked ? kMaskCost : px.energy;
            }
            __m256 prev_l = _mm256_loadu_ps(prev_row + c - 1);
            __m256 prev_m = _mm256_loadu_ps(prev_row + c);
            __m256 prev_r = _mm256_loadu_ps(prev_row + c + 1);
            __m256 cost   = _mm256_load_ps(cost_block);

            // Mirrors scalar_cell's dc = -1, 0, +1 order and strict "<"
            // comparison exactly, so ties resolve to the same (leftmost)
            // neighbor as the scalar loop.
            __m256 best = prev_l;
            __m256 offset = _mm256_set1_ps(-1.0f);

            __m256 mask_m = _mm256_cmp_ps(prev_m, best, _CMP_LT_OQ);
            best = _mm256_blendv_ps(best, prev_m, mask_m);
            offset = _mm256_blendv_ps(offset, _mm256_setzero_ps(), mask_m);

            __m256 mask_r = _mm256_cmp_ps(prev_r, best, _CMP_LT_OQ);
            best = _mm256_blendv_ps(best, prev_r, mask_r);
            offset = _mm256_blendv_ps(offset, _mm256_set1_ps(1.0f), mask_r);

            __m256 dp_val = _mm256_add_ps(best, cost);
            _mm256_storeu_ps(cur_row + c, dp_val);

            __m256i offset_i = _mm256_cvttps_epi32(offset);
            __m256i c_idx = _mm256_add_epi32(
                _mm256_set1_epi32(static_cast<int>(c)),
                _mm256_setr_epi32(0, 1, 2, 3, 4, 5, 6, 7));
            __m256i parent_i = _mm256_add_epi32(c_idx, offset_i);
            _mm256_storeu_si256(reinterpret_cast<__m256i*>(cur_parent + c), parent_i);
        }
#elif defined(HIE_SIMD_SEAM_NEON)
        const std::size_t simd_end =
            c + (interior_end > c ? ((interior_end - c) / 4) * 4 : 0);
        for (; c < simd_end; c += 4) {
            float cost_block[4];
            for (int k = 0; k < 4; ++k) {
                const SeamPixel& px = row_px[c + k];
                cost_block[k] = px.masked ? kMaskCost : px.energy;
            }
            float32x4_t prev_l = vld1q_f32(prev_row + c - 1);
            float32x4_t prev_m = vld1q_f32(prev_row + c);
            float32x4_t prev_r = vld1q_f32(prev_row + c + 1);
            float32x4_t cost   = vld1q_f32(cost_block);

            float32x4_t best = prev_l;
            int32x4_t offset = vdupq_n_s32(-1);

            uint32x4_t mask_m = vcltq_f32(prev_m, best);
            best = vbslq_f32(mask_m, prev_m, best);
            offset = vbslq_s32(mask_m, vdupq_n_s32(0), offset);

            uint32x4_t mask_r = vcltq_f32(prev_r, best);
            best = vbslq_f32(mask_r, prev_r, best);
            offset = vbslq_s32(mask_r, vdupq_n_s32(1), offset);

            float32x4_t dp_val = vaddq_f32(best, cost);
            vst1q_f32(cur_row + c, dp_val);

            int32_t c_idx_arr[4] = {
                static_cast<int32_t>(c), static_cast<int32_t>(c) + 1,
                static_cast<int32_t>(c) + 2, static_cast<int32_t>(c) + 3};
            int32x4_t c_idx = vld1q_s32(c_idx_arr);
            int32x4_t parent_v = vaddq_s32(c_idx, offset);
            vst1q_s32(cur_parent + c, parent_v);
        }
#endif

        for (; c < cols; ++c) {
            scalar_cell(c);
        }
    }

    // Find minimum energy column in the last row
    std::size_t min_col = 0;
    float       min_val = std::numeric_limits<float>::infinity();
    for (std::size_t c = 0; c < cols; ++c) {
        float v = dp[(rows - 1) * cols + c];
        if (v < min_val) {
            min_val = v;
            min_col = c;
        }
    }

    // Back-trace the seam
    result.seam_x.resize(rows);
    result.seam_x[rows - 1] = static_cast<int>(min_col);

    for (int r = static_cast<int>(rows) - 2; r >= 0; --r) {
        int next_c = result.seam_x[r + 1];
        result.seam_x[r] = parent[(r + 1) * cols + next_c];
    }

    result.total_energy = min_val;
    result.success = true;
    return result;
}

// ─── GNC-TLS 2D Alignment ────────────────────────────────────────────────────

AlignmentResult solve_alignment_gnc(
        const std::vector<Correspondence>& correspondences,
        std::uint32_t gnc_iterations,
        float inlier_threshold) {
    AlignmentResult result;
    result.success = false;

    if (correspondences.size() < 3) {
        result.error = "Need at least 3 correspondences for [tx, ty, scale] alignment";
        return result;
    }

    // GNC-TLS: iteratively re-weighted least squares for [tx, ty, scale].
    // Weight function: w_i = 1 / (r_i^2 + mu) where mu is annealed from
    // a large value (convex) toward 0 (TLS / near-truncated).

    std::size_t N = correspondences.size();
    std::vector<float> weights(N, 1.0f);

    float tx = 0.f, ty = 0.f, scale = 1.f;

    float mu = inlier_threshold * inlier_threshold * 9.0f; // initial mu (convex)
    float mu_min = 1e-4f;
    float mu_factor = std::pow(mu_min / mu, 1.0f / gnc_iterations);

    for (std::uint32_t iter = 0; iter < gnc_iterations; ++iter) {
        // Weighted least squares for [tx, ty, scale] with current weights.
        // Model: dst_x = scale * src_x + tx
        //        dst_y = scale * src_y + ty
        // Linearise as normal equations over the 3-parameter vector.

        double sw   = 0, swx = 0, swy = 0, swxx = 0;
        double swdx = 0, swdy = 0, swxdx = 0;

        for (std::size_t i = 0; i < N; ++i) {
            float w = weights[i];
            float sx = correspondences[i].src_x;
            float sy = correspondences[i].src_y;
            float dx = correspondences[i].dst_x;
            float dy = correspondences[i].dst_y;

            sw    += w;
            swx   += w * sx;
            swy   += w * sy;
            swxx  += w * (sx * sx + sy * sy);
            swdx  += w * dx;
            swdy  += w * dy;
            swxdx += w * (sx * dx + sy * dy);
        }

        if (std::abs(sw) < 1e-12) break;
        // Center both point sets before estimating scale. This separates the
        // isotropic scale from translation and avoids bias when coordinates
        // are far from the origin (the common image-canvas case).
        const double mean_x = swx / sw;
        const double mean_y = swy / sw;
        const double mean_dx = swdx / sw;
        const double mean_dy = swdy / sw;
        double centered_cross = 0.0;
        double centered_source = 0.0;
        for (std::size_t i = 0; i < N; ++i) {
            const double w = weights[i];
            const double sx = correspondences[i].src_x - mean_x;
            const double sy = correspondences[i].src_y - mean_y;
            const double dx = correspondences[i].dst_x - mean_dx;
            const double dy = correspondences[i].dst_y - mean_dy;
            centered_cross += w * (sx * dx + sy * dy);
            centered_source += w * (sx * sx + sy * sy);
        }
        if (std::abs(centered_source) < 1e-12) break;
        scale = static_cast<float>(centered_cross / centered_source);

        // Recover translation from the weighted centroids.
        tx = static_cast<float>((swdx - scale * swx) / sw);
        ty = static_cast<float>((swdy - scale * swy) / sw);

        // Update weights using GNC schedule
        for (std::size_t i = 0; i < N; ++i) {
            float sx = correspondences[i].src_x;
            float sy = correspondences[i].src_y;
            float rx = scale * sx + tx - correspondences[i].dst_x;
            float ry = scale * sy + ty - correspondences[i].dst_y;
            float r2 = rx * rx + ry * ry;
            weights[i] = mu / (r2 + mu);
        }

        mu *= mu_factor;
        if (mu < mu_min) mu = mu_min;
    }

    // Count inliers and compute RMS residual
    float rms = 0.f;
    std::uint32_t inliers = 0;
    for (std::size_t i = 0; i < N; ++i) {
        float sx = correspondences[i].src_x;
        float sy = correspondences[i].src_y;
        float rx = scale * sx + tx - correspondences[i].dst_x;
        float ry = scale * sy + ty - correspondences[i].dst_y;
        float r2 = rx * rx + ry * ry;
        rms += r2;
        if (std::sqrt(r2) <= inlier_threshold) ++inliers;
    }
    rms = std::sqrt(rms / N);

    result.model         = {tx, ty, scale};
    result.residual      = rms;
    result.inlier_count  = inliers;
    result.success       = true;
    return result;
}

// ─── Convex Color Harmonization ───────────────────────────────────────────────

ColorHarmonizationResult solve_color_harmonization(
        const LayerColorStats& source,
        const LayerColorStats& target) {
    ColorHarmonizationResult result;
    result.success = false;

    // Affine per-channel transfer: out = alpha * in + beta
    // alpha = target_std / source_std  (scale)
    // beta  = target_mean - alpha * source_mean  (shift)
    // This is the Reinhard et al. (2001) colour transfer in Lab, extended
    // to enforce non-clipping via clamped beta.

    auto safe_div = [](float a, float b) -> float {
        return std::abs(b) < 1e-7f ? 1.f : a / b;
    };

    result.alpha_l = safe_div(target.std_l, source.std_l);
    result.beta_l  = target.mean_l - result.alpha_l * source.mean_l;

    result.alpha_a = safe_div(target.std_a, source.std_a);
    result.beta_a  = target.mean_a - result.alpha_a * source.mean_a;

    result.alpha_b = safe_div(target.std_b, source.std_b);
    result.beta_b  = target.mean_b - result.alpha_b * source.mean_b;

    // Clamp beta so that the minimum source value stays non-negative (L channel)
    // and to prevent clipping at the high end. Simple convex projection onto [0,100].
    //
    // `hi` must be recomputed after the low-end correction: the two branches both
    // mutate `beta`, so checking the high end against a `hi` computed from the
    // pre-correction `beta` let the corrections stack instead of compose (e.g.
    // alpha=2 could clamp beta once for the low bound, then clamp it a second,
    // unrelated time for a high bound reading that was already stale). Note this
    // is still a pure shift (alpha is never rescaled), so for alpha far from 1
    // there may be no beta that satisfies both bounds at once — in that case this
    // clamps as close as a single shift can get, biased toward the bound whose
    // violation is resolved second (currently the high end).
    auto clamp_beta = [&](float alpha, float& beta, float src_min, float src_max,
                          float out_min, float out_max) {
        float lo = alpha * src_min + beta;
        if (lo < out_min) beta += out_min - lo;
        float hi = alpha * src_max + beta;
        if (hi > out_max) beta -= hi - out_max;
    };

    clamp_beta(result.alpha_l, result.beta_l, 0.f, 100.f, 0.f, 100.f);
    clamp_beta(result.alpha_a, result.beta_a, -128.f, 127.f, -128.f, 127.f);
    clamp_beta(result.alpha_b, result.beta_b, -128.f, 127.f, -128.f, 127.f);

    result.success = true;
    return result;
}

}  // namespace hybrid_image_editor
