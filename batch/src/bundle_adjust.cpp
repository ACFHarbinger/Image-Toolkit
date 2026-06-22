// ---------------------------------------------------------------------------
// batch/src/bundle_adjust.cpp
//
// Affine bundle adjustment: LM solver, GNC-TLS outer loop, spanning-tree
// inlier filter, adaptive f_scale, wave correct.
//
// Replaces:
//   alignment/bundle_adjust.py  :: _bundle_adjust_affine,
//                                   _spanning_tree_inlier_filter,
//                                   _compute_adaptive_f_scale
//
// Implementation roadmap: Phase 3.
// See moon/roadmaps/asp_cpp_migration.md §batch::bundle_adjust
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"
#include "batch/affine_types.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// bundle_adjust_affine
//
// Full affine bundle adjustment:
//   - Optional GNC-TLS outer loop (8 iterations, Geman-McClure weights)
//   - Eigen LDLT inner solve: (J^T W J) Δx = J^T W r
//   - Cauchy robust loss on inner iterations
//   - Optional adaptive f_scale re-solve
//
// Args
// ----
// edges            : list of Edge dicts {"i","j","dx","dy","weight"}
// N                : int, number of frames
// f_scale          : float, Cauchy loss scale (default 10.0)
// use_gnc          : bool, enable GNC-TLS outer loop
// adaptive_f_scale : bool, re-solve with median_residual-scaled f
//
// Returns
// -------
// list of AffineParams dicts {"tx","ty","scale","rotation","frame_idx"}
// ---------------------------------------------------------------------------
static py::list bundle_adjust_affine(
    py::list edges,
    int      N,
    float    f_scale          = 10.0f,
    bool     use_gnc          = true,
    bool     adaptive_f_scale = true)
{
    // TODO (Phase 3):
    //   1. Parse edges → std::vector<Edge>
    //   2. Build normal equations J, r, W
    //   3. GNC-TLS outer loop if use_gnc
    //   4. Eigen LDLT solve
    //   5. Adaptive f_scale re-solve if adaptive_f_scale
    //   6. Return affines as list of dicts
    BATCH_NOT_IMPLEMENTED("bundle_adjust.bundle_adjust_affine");
}

// ---------------------------------------------------------------------------
// spanning_tree_inlier_filter
//
// Kruskal maximum spanning tree (highest-weight-first) with Union-Find.
// BFS from frame 0 propagates reference translations.
// Drops edges where predicted − observed displacement > inlier_threshold.
// Falls back to original edges if graph disconnects or < max(2,N-1) inliers.
// ---------------------------------------------------------------------------
static py::list spanning_tree_inlier_filter(
    py::list edges,
    int      N,
    float    inlier_threshold = 50.0f)
{
    // TODO (Phase 3): Union-Find + BFS inlier filter.
    BATCH_NOT_IMPLEMENTED("bundle_adjust.spanning_tree_inlier_filter");
}

// ---------------------------------------------------------------------------
// compute_adaptive_f_scale
//
// After an initial solve, compute adaptive_scale = max(floor, 2 × median_residual).
// Returns float.
// ---------------------------------------------------------------------------
static float compute_adaptive_f_scale(
    py::list edges,
    py::list affines,
    float    floor_scale = 5.0f)
{
    // TODO (Phase 3): compute residuals, take median, apply heuristic.
    BATCH_NOT_IMPLEMENTED("bundle_adjust.compute_adaptive_f_scale");
}

// ---------------------------------------------------------------------------
// register_bundle_adjust — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_bundle_adjust(py::module_& m) {
    m.doc() = R"doc(
        batch.bundle_adjust — Affine bundle adjustment via Eigen LDLT.

        Functions
        ---------
        bundle_adjust_affine(edges, N, f_scale, use_gnc, adaptive_f_scale) -> list[dict]
        spanning_tree_inlier_filter(edges, N, inlier_threshold) -> list[dict]
        compute_adaptive_f_scale(edges, affines, floor_scale) -> float
    )doc";

    m.def("bundle_adjust_affine", &bundle_adjust_affine,
        py::arg("edges"),
        py::arg("N"),
        py::arg("f_scale")          = 10.0f,
        py::arg("use_gnc")          = true,
        py::arg("adaptive_f_scale") = true,
        R"doc(
            Full affine bundle adjustment.

            Args
            ----
            edges   : list[dict]  — each has "i","j","dx","dy","weight"
            N       : int  — number of frames
            f_scale : float  — Cauchy robust loss scale
            use_gnc : bool  — enable GNC-TLS outer loop (8 iters)
            adaptive_f_scale : bool  — re-solve with median-residual f

            Returns
            -------
            list[dict] with keys "tx","ty","scale","rotation","frame_idx"
        )doc");

    m.def("spanning_tree_inlier_filter", &spanning_tree_inlier_filter,
        py::arg("edges"),
        py::arg("N"),
        py::arg("inlier_threshold") = 50.0f,
        R"doc(
            Kruskal maximum spanning tree inlier filter.

            Drops edges with predicted–observed displacement > inlier_threshold.
            Falls back to original edges if graph becomes disconnected.

            Returns list[dict] — filtered edges.
        )doc");

    m.def("compute_adaptive_f_scale", &compute_adaptive_f_scale,
        py::arg("edges"),
        py::arg("affines"),
        py::arg("floor_scale") = 5.0f,
        R"doc(
            Compute adaptive_scale = max(floor_scale, 2 × median_residual_px).

            Returns float.
        )doc");
}
