// ---------------------------------------------------------------------------
// batch/src/wave_correct.cpp
//
// Linear drift subtraction via Eigen least-squares (polyfit degree 1).
//
// Replaces:
//   core/pipeline.py  :: _wave_correct_affines  (§4.3)
//
// Implementation roadmap: Phase 3.
// See moon/roadmaps/asp_cpp_migration.md §base::wave_correct
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <Eigen/Dense>

#include "common.hpp"
#include "affine_types.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

namespace py = pybind11;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
static constexpr float WAVE_CORRECT_MIN_RANGE_PX = 5.0f;

// ---------------------------------------------------------------------------
// wave_correct_values_impl (pure C++)
//
// Fit a linear trend via Eigen::HouseholderQR on the Vandermonde matrix
//   A = [[0, 1], [1, 1], ..., [N-1, 1]]
//   b = vals
// Subtract the trend and anchor the corrected sequence at vals[0].
//
// Equivalent to Python:
//   slope, intercept = np.polyfit(frame_idx, vals, 1)
//   trend = slope * frame_idx + intercept
//   corrected = vals - trend + vals[0]
//
// Returns corrected_vals unchanged when N < 3 or ptp(vals) < min_range_px.
// ---------------------------------------------------------------------------
std::vector<float> wave_correct_values_impl(
    const std::vector<float>& vals,
    float min_range_px)
{
    int N = static_cast<int>(vals.size());
    if (N < 3) return vals;

    float vmin = *std::min_element(vals.begin(), vals.end());
    float vmax = *std::max_element(vals.begin(), vals.end());
    if ((vmax - vmin) < min_range_px) return vals;

    // Build Vandermonde matrix A and RHS vector b
    Eigen::MatrixXf A(N, 2);
    Eigen::VectorXf b(N);
    for (int i = 0; i < N; ++i) {
        A(i, 0) = static_cast<float>(i);
        A(i, 1) = 1.0f;
        b(i)    = vals[i];
    }

    // Solve via least-squares (Householder QR — well-conditioned for small N)
    Eigen::Vector2f coeffs = A.householderQr().solve(b);
    float slope     = coeffs(0);
    float intercept = coeffs(1);

    // Subtract linear trend; re-anchor at trend(0)=intercept so corrected[0]==vals[0]
    std::vector<float> corrected(N);
    for (int i = 0; i < N; ++i) {
        float trend   = slope * static_cast<float>(i) + intercept;
        corrected[i]  = vals[i] - trend + intercept;
    }
    return corrected;
}

// ---------------------------------------------------------------------------
// Python bindings
// ---------------------------------------------------------------------------
#ifndef BATCH_TESTS

// ---------------------------------------------------------------------------
// wave_correct_affines — Python wrapper
//
// Input  : list of (2, 3) float32 numpy affine matrices
// Output : list of (2, 3) float32 numpy affine matrices with tx or ty corrected
//
// axis = "vertical"   → correct tx (cross-axis drift for vertical scroll)
// axis = "horizontal" → correct ty (cross-axis drift for horizontal scroll)
// ---------------------------------------------------------------------------
static py::list wave_correct_affines(
    py::list    affines_py,
    std::string axis         = "vertical",
    float       min_range_px = WAVE_CORRECT_MIN_RANGE_PX)
{
    bool correct_tx = (axis != "horizontal");

    // Extract the sequence to correct
    std::vector<float> vals;
    vals.reserve(py::len(affines_py));

    // Also keep original arrays for reconstruction
    std::vector<py::array_t<float, py::array::c_style | py::array::forcecast>> arrs;
    for (auto item : affines_py) {
        auto arr = item.cast<py::array_t<float, py::array::c_style | py::array::forcecast>>();
        BATCH_CHECK(arr.ndim() == 2 && arr.shape(0) >= 2 && arr.shape(1) >= 3,
                    "wave_correct_affines: each affine must be a (2,3) float32 array");
        auto a = arr.unchecked<2>();
        vals.push_back(correct_tx ? a(0, 2) : a(1, 2));
        arrs.push_back(arr);
    }

    std::vector<float> corrected = wave_correct_values_impl(vals, min_range_px);

    // Build output list
    py::list out;
    for (int i = 0; i < static_cast<int>(arrs.size()); ++i) {
        const auto& src_arr = arrs[i];
        auto src = src_arr.unchecked<2>();

        // Deep copy: allocate owned (2, 3) float array
        auto result = py::array_t<float>({(ssize_t)2, (ssize_t)3});
        auto dst    = result.mutable_unchecked<2>();

        for (ssize_t r = 0; r < 2; ++r)
            for (ssize_t c = 0; c < 3; ++c)
                dst(r, c) = src(r, c);

        // Overwrite the corrected axis
        if (correct_tx) dst(0, 2) = corrected[i];
        else            dst(1, 2) = corrected[i];

        out.append(result);
    }
    return out;
}

// ---------------------------------------------------------------------------
// register_wave_correct — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_wave_correct(py::module_& m) {
    m.doc() = R"doc(
        batch.wave_correct — Linear drift subtraction via Eigen polyfit.

        Functions
        ---------
        wave_correct_affines(affines, axis="vertical", min_range_px=5.0)
            -> list of (2,3) float32 numpy arrays

        Accepts a list of (2, 3) float32 numpy affine matrices; returns the
        same list with the cross-axis drift subtracted.
    )doc";

    m.def("wave_correct_affines", &wave_correct_affines,
        py::arg("affines"),
        py::arg("axis")          = "vertical",
        py::arg("min_range_px")  = WAVE_CORRECT_MIN_RANGE_PX,
        R"doc(
            §4.3 — Subtract linear drift from the tx or ty affine sequence.

            Fits a linear trend via Eigen HouseholderQR (equivalent to
            numpy.polyfit(frame_idx, vals, 1)) and subtracts it, anchoring
            the corrected sequence at the original first-frame value.

            Args
            ----
            affines      : list of (2, 3) float32 numpy affine matrices
            axis         : "vertical" → correct tx; "horizontal" → correct ty
            min_range_px : skip correction if ptp(vals) < threshold

            Returns corrected list of (2, 3) float32 numpy arrays.
        )doc");
}

#endif // BATCH_TESTS
