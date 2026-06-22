#pragma once

// ---------------------------------------------------------------------------
// batch/image_utils.hpp
//
// Lightweight image format helpers shared across batch submodules.
// All functions operate on cv::Mat and do not call into Python.
// ---------------------------------------------------------------------------

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <stdexcept>

namespace batch {

// ---------------------------------------------------------------------------
// Color space conversions (in-place or returning new mat)
// ---------------------------------------------------------------------------

/// Convert a BGR uint8 mat to luma (single channel float32, range [0,255]).
/// Uses Rec.601 luminance weights: 0.114B + 0.587G + 0.299R
inline cv::Mat bgr_to_luma(const cv::Mat& bgr) {
    if (bgr.channels() == 1) {
        cv::Mat out;
        bgr.convertTo(out, CV_32F);
        return out;
    }
    if (bgr.channels() != 3)
        throw std::invalid_argument("bgr_to_luma: expected 1 or 3-channel mat");
    cv::Mat gray;
    cv::cvtColor(bgr, gray, cv::COLOR_BGR2GRAY);
    cv::Mat out;
    gray.convertTo(out, CV_32F);
    return out;
}

/// Convert BGRA uint8 mat to BGR (drop alpha channel).
inline cv::Mat bgra_to_bgr(const cv::Mat& bgra) {
    if (bgra.channels() == 3) return bgra.clone();
    if (bgra.channels() != 4)
        throw std::invalid_argument("bgra_to_bgr: expected 4-channel mat");
    cv::Mat bgr;
    cv::cvtColor(bgra, bgr, cv::COLOR_BGRA2BGR);
    return bgr;
}

/// Convert BGR uint8 to BGRA (alpha=255).
inline cv::Mat bgr_to_bgra(const cv::Mat& bgr) {
    if (bgr.channels() == 4) return bgr.clone();
    cv::Mat bgra;
    cv::cvtColor(bgr, bgra, cv::COLOR_BGR2BGRA);
    return bgra;
}

// ---------------------------------------------------------------------------
// Mask helpers
// ---------------------------------------------------------------------------

/// Build a binary uint8 mask from a float32 mat: 255 where value >= threshold.
inline cv::Mat float_to_mask(const cv::Mat& f32, float threshold = 0.5f) {
    cv::Mat out;
    cv::threshold(f32, out, threshold, 255.0, cv::THRESH_BINARY);
    out.convertTo(out, CV_8U);
    return out;
}

/// Dilate a binary mask by `radius` pixels using an elliptical structuring element.
inline cv::Mat dilate_mask(const cv::Mat& mask, int radius) {
    if (radius <= 0) return mask.clone();
    cv::Mat se = cv::getStructuringElement(
        cv::MORPH_ELLIPSE,
        cv::Size(2 * radius + 1, 2 * radius + 1));
    cv::Mat out;
    cv::dilate(mask, out, se);
    return out;
}

// ---------------------------------------------------------------------------
// Numeric helpers
// ---------------------------------------------------------------------------

/// Clamp a float to [lo, hi].
inline float clampf(float v, float lo, float hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

/// Safe division: returns numerator / denominator, or fallback if denominator
/// is within epsilon of zero.
inline float safe_div(float num, float den, float fallback = 0.0f,
                      float eps = 1e-6f) {
    return (std::abs(den) < eps) ? fallback : num / den;
}

} // namespace batch
