#pragma once

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

/// @file exact_solvers.hpp
/// @brief Exact numerical solvers: DP seam routing, GNC-TLS layer alignment,
///        and convex color harmonization.

namespace hybrid_image_editor {

// ─── Seam Routing ─────────────────────────────────────────────────────────────

/// Cost pixel for seam energy minimization.
struct SeamPixel {
    float energy;  ///< Edge/gradient energy at this pixel
    bool  masked;  ///< True → pixel belongs to a protected character mask (infinite cost)
};

/// Result of an optimal seam routing computation.
struct SeamResult {
    std::vector<int> seam_x;  ///< x-coordinate of the seam at each row (vertical seam)
    float total_energy;        ///< Sum of energy along the chosen seam
    bool  success;
    std::string error;
};

/// @brief Dynamic-programming optimal seam routing (Min-Cut / Viterbi path).
///
/// Computes the minimum-energy vertical seam through `energy_grid` of
/// size (rows × cols). Pixels with `SeamPixel::masked == true` carry
/// an infinite cost penalty, preventing seams from severing protected
/// character regions.
///
/// @param energy_grid  Row-major energy grid (rows × cols).
/// @param rows         Number of pixel rows.
/// @param cols         Number of pixel columns.
/// @return SeamResult  Optimal seam x-coordinates and total energy.
SeamResult solve_seam(
    const std::vector<SeamPixel>& energy_grid,
    std::size_t rows,
    std::size_t cols);

// ─── Layer Alignment (GNC-TLS Translation + Scale) ────────────────────────────

/// A 2D feature correspondence used in bundle adjustment.
struct Correspondence {
    float src_x, src_y;  ///< Feature location in the source frame
    float dst_x, dst_y;  ///< Matching location in the target frame
};

/// 2D Translation + Scale motion model: [tx, ty, scale].
struct MotionModel2DTS {
    float tx    = 0.f;  ///< Horizontal translation (pixels)
    float ty    = 0.f;  ///< Vertical translation (pixels)
    float scale = 1.f;  ///< Uniform scale factor
};

/// Result of layer alignment.
struct AlignmentResult {
    MotionModel2DTS model;
    float           residual;  ///< RMS reprojection error after GNC
    std::uint32_t   inlier_count;
    bool            success;
    std::string     error;
};

/// @brief GNC-TLS robust 2D alignment (translation + scale only).
///
/// Fits a [tx, ty, scale] motion model to the given correspondences using
/// Graduated Non-Convexity with Total Least Squares (GNC-TLS) outlier
/// rejection.  Prevents homography rotational warping on 2D lateral-pan
/// anime sequences.
///
/// @param correspondences  List of src→dst point pairs.
/// @param gnc_iterations   Number of GNC μ-continuation steps.
/// @param inlier_threshold Pixel distance threshold for inlier classification.
/// @return AlignmentResult Fitted motion model and diagnostics.
AlignmentResult solve_alignment_gnc(
    const std::vector<Correspondence>& correspondences,
    std::uint32_t gnc_iterations    = 8,
    float         inlier_threshold  = 3.0f);

// ─── Convex Color Harmonization ───────────────────────────────────────────────

/// Per-layer color statistics for harmonization input.
struct LayerColorStats {
    float mean_l, mean_a, mean_b;  ///< CIELab mean
    float std_l,  std_a,  std_b;   ///< CIELab standard deviation
};

/// Result of global color harmonization.
struct ColorHarmonizationResult {
    /// Affine transfer coefficients per channel: out = alpha * in + beta.
    float alpha_l, beta_l;
    float alpha_a, beta_a;
    float alpha_b, beta_b;
    bool  success;
    std::string error;
};

/// @brief Convex color harmonization matching a target layer's palette.
///
/// Solves for per-channel affine transfer coefficients (alpha, beta) that
/// map `source` statistics toward `target` statistics while enforcing
/// non-clipping constraints ([0, 255] or [0, 1] depending on scale).
///
/// @param source   Color statistics of the layer to be adjusted.
/// @param target   Color statistics of the reference/target layer.
/// @return ColorHarmonizationResult  Affine transfer coefficients per channel.
ColorHarmonizationResult solve_color_harmonization(
    const LayerColorStats& source,
    const LayerColorStats& target);

}  // namespace hybrid_image_editor
