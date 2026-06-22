// ---------------------------------------------------------------------------
// batch/src/validation.cpp
//
// Affine sequence validation: monotone step, ratio, gap checks.
//
// Replaces:
//   core/validation.py  :: _validate_affines, _compute_adaptive_min_gap,
//                          _compute_adaptive_rot_scale
//
// Implementation roadmap: Phase 3.
// See moon/roadmaps/asp_cpp_migration.md §batch::validation
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"
#include "batch/affine_types.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// validate_affines
//
// Checks:
//   1. Monotone step: all |ty[i+1]-ty[i]| in same direction and > min_step
//   2. Ratio: max(steps) / min(steps) < max_ratio
//   3. Gap: no individual step > max_gap
//
// Returns (bool ok, str reason)  — reason="" if ok.
// ---------------------------------------------------------------------------
static py::tuple validate_affines(
    py::list affines,
    float    min_step  = 25.0f,
    float    max_ratio = 8.0f,
    float    max_gap   = 500.0f)
{
    // TODO (Phase 3): iterate affines, compute step sequence, apply three checks.
    BATCH_NOT_IMPLEMENTED("validation.validate_affines");
}

// ---------------------------------------------------------------------------
// compute_adaptive_min_gap
//
// Returns max(20.0, canvas_span / (N × 3)) where canvas_span is derived
// from the ty range of the affine sequence.
// ---------------------------------------------------------------------------
static float compute_adaptive_min_gap(py::list affines)
{
    // TODO (Phase 3): extract ty values, compute span, apply formula.
    BATCH_NOT_IMPLEMENTED("validation.compute_adaptive_min_gap");
}

// ---------------------------------------------------------------------------
// compute_adaptive_rot_scale
//
// Check rotation and scale deviation across the affine sequence.
// Returns dict {"ok": bool, "max_rot_deg": float, "max_scale_ratio": float}.
// ---------------------------------------------------------------------------
static py::dict compute_adaptive_rot_scale(py::list affines)
{
    // TODO (Phase 3): extract rotation/scale from affines, compute deviations.
    BATCH_NOT_IMPLEMENTED("validation.compute_adaptive_rot_scale");
}

// ---------------------------------------------------------------------------
// register_validation — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_validation(py::module_& m) {
    m.doc() = R"doc(
        batch.validation — Affine sequence validation.

        Functions
        ---------
        validate_affines(affines, min_step, max_ratio, max_gap) -> (bool, str)
        compute_adaptive_min_gap(affines) -> float
        compute_adaptive_rot_scale(affines) -> dict
    )doc";

    m.def("validate_affines", &validate_affines,
        py::arg("affines"),
        py::arg("min_step")  = 25.0f,
        py::arg("max_ratio") = 8.0f,
        py::arg("max_gap")   = 500.0f,
        R"doc(
            Validate an affine sequence for monotone step, ratio, and gap constraints.

            Args
            ----
            affines   : list[dict]  — AffineParams dicts (must have "ty")
            min_step  : float  — minimum per-frame step (pixels)
            max_ratio : float  — max(steps)/min(steps) upper bound
            max_gap   : float  — maximum individual step (pixels)

            Returns
            -------
            (ok: bool, reason: str)  — reason is "" when ok is True.
        )doc");

    m.def("compute_adaptive_min_gap", &compute_adaptive_min_gap,
        py::arg("affines"),
        R"doc(
            Compute max(20.0, canvas_span / (N × 3)) from the ty sequence.

            Returns float (pixels).
        )doc");

    m.def("compute_adaptive_rot_scale", &compute_adaptive_rot_scale,
        py::arg("affines"),
        R"doc(
            Compute maximum rotation deviation (degrees) and scale ratio across sequence.

            Returns dict {"ok": bool, "max_rot_deg": float, "max_scale_ratio": float}.
        )doc");
}
