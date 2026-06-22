// ---------------------------------------------------------------------------
// batch/src/wave_correct.cpp
//
// Linear drift subtraction via least-squares polynomial fit.
//
// Replaces:
//   alignment/bundle_adjust.py  :: _wave_correct_affines
//
// Also provides a thin wrapper for cv::detail::waveCorrect (Phase 4).
//
// Implementation roadmap: Phase 3.
// See moon/roadmaps/asp_cpp_migration.md §batch::wave_correct
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"
#include "batch/affine_types.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// wave_correct_affines
//
// Subtract the linear drift from the tx or ty sequence:
//   1. Extract [tx_i] or [ty_i] from affine dicts
//   2. Fit linear trend: numpy.polyfit(idx, values, 1) equivalent
//      via Eigen householderQr on Vandermonde matrix [[i, 1] for i in range(N)]
//   3. Subtract trend: values_corrected[i] = values[i] - (slope*i + intercept)
//   4. Guard: only fire when ptp(values) > min_range_px
//
// Args
// ----
// affines      : list[dict] with "tx" and "ty" keys
// axis         : "vertical" (correct ty) or "horizontal" (correct tx)
// min_range_px : minimum ptp to apply correction (default 5.0)
//
// Returns list[dict] — corrected affines (same structure as input).
// ---------------------------------------------------------------------------
static py::list wave_correct_affines(
    py::list    affines,
    std::string axis          = "vertical",
    float       min_range_px  = 5.0f)
{
    // TODO (Phase 3): Eigen householderQr linear fit; subtract trend.
    BATCH_NOT_IMPLEMENTED("wave_correct.wave_correct_affines");
}

// ---------------------------------------------------------------------------
// register_wave_correct — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_wave_correct(py::module_& m) {
    m.doc() = R"doc(
        batch.wave_correct — Linear drift subtraction via Eigen polyfit.

        Functions
        ---------
        wave_correct_affines(affines, axis, min_range_px) -> list[dict]
    )doc";

    m.def("wave_correct_affines", &wave_correct_affines,
        py::arg("affines"),
        py::arg("axis")         = "vertical",
        py::arg("min_range_px") = 5.0f,
        R"doc(
            Subtract linear drift from the tx or ty affine sequence.

            Equivalent to numpy.polyfit(frame_idx, values, 1) but implemented
            via Eigen::HouseholderQR for speed with small N.

            Args
            ----
            affines      : list[dict] with "tx" and "ty" fields
            axis         : "vertical" (subtract from ty) | "horizontal" (from tx)
            min_range_px : skip correction if ptp(values) < this threshold

            Returns list[dict] with corrected "tx"/"ty" values.
        )doc");
}
