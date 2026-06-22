// ---------------------------------------------------------------------------
// batch/src/matching.cpp
//
// Phase correlation, edge graph construction, static edge rejection.
//
// Replaces:
//   flow/cam_flow.py       :: _phase_correlate, bg_masked_phase_correlate
//   alignment/matching.py  :: edge graph construction, bg filtering,
//                             post-match gates (§1.36, §1.38, §1.47, §1.48,
//                             §1.49, §2.14), _filter_edges, _reject_static_edges,
//                             _compute_adaptive_min_disp, _spatial_dedup_frames
//
// Implementation roadmap: Phase 3 (alignment hot path).
// See moon/roadmaps/asp_cpp_migration.md §batch::matching
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"
#include "batch/affine_types.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// phase_correlate_masked
//
// Compute sub-pixel phase correlation between two luma planes, optionally
// masking background pixels before computing the cross-power spectrum.
//
// Args
// ----
// frame_a_gray : ndarray uint8 (H, W) — luma plane of frame A
// frame_b_gray : ndarray uint8 (H, W) — luma plane of frame B
// bg_mask_a    : ndarray uint8 (H, W) or None — 0 = background, 255 = foreground
// bg_mask_b    : ndarray uint8 (H, W) or None
//
// Returns
// -------
// dict with keys "dx" (float), "dy" (float), "response" (float)
// ---------------------------------------------------------------------------
static py::dict phase_correlate_masked(
    py::array_t<uint8_t> frame_a_gray,
    py::array_t<uint8_t> frame_b_gray,
    py::object           bg_mask_a,   // None or ndarray uint8
    py::object           bg_mask_b)
{
    // TODO (Phase 3): implement via cv::phaseCorrelate + Hanning window +
    // background masking + high-pass (subtract 3×3 box blur).
    BATCH_NOT_IMPLEMENTED("matching.phase_correlate_masked");
}

// ---------------------------------------------------------------------------
// build_edge_graph
//
// Filter raw per-pair match dicts through post-match gates and return a
// pruned list of Edge dicts suitable for bundle adjustment.
//
// Gates applied (see roadmap §batch::matching):
//   §1.36 spread MAD, §1.38 bg-ratio, §1.47 sign consistency,
//   §1.48 CV, §1.49 adj-min, §2.14 triangular consistency
//
// Args
// ----
// raw_matches : list of dict, one per frame pair, each containing
//               "src", "dst", "pts_a", "pts_b", "weights"
// bg_masks    : list of ndarray uint8 (H, W), one per frame
// N           : int, total number of frames
//
// Returns
// -------
// list of Edge dicts {"i","j","dx","dy","weight","type"}
// ---------------------------------------------------------------------------
static py::list build_edge_graph(
    py::list  raw_matches,
    py::list  bg_masks,
    int       N)
{
    // TODO (Phase 3): implement all post-match gates via Eigen / STL.
    BATCH_NOT_IMPLEMENTED("matching.build_edge_graph");
}

// ---------------------------------------------------------------------------
// reject_static_edges
//
// Drop edges where both |dx| < min_disp_px and |dy| < min_disp_px.
// (§1.2A static edge rejection)
//
// Returns filtered list of Edge dicts.
// ---------------------------------------------------------------------------
static py::list reject_static_edges(
    py::list edges,
    float    min_disp_px)
{
    // TODO (Phase 3): iterate edges, drop those with |dx|<min_disp_px AND |dy|<min_disp_px.
    BATCH_NOT_IMPLEMENTED("matching.reject_static_edges");
}

// ---------------------------------------------------------------------------
// compute_adaptive_min_disp
//
// Estimate the minimum displacement threshold from the distribution of
// observed edge displacements (e.g. median × 0.3 heuristic from §1.2A).
//
// Returns float.
// ---------------------------------------------------------------------------
static float compute_adaptive_min_disp(py::list edges)
{
    // TODO (Phase 3): compute from edge displacement distribution.
    BATCH_NOT_IMPLEMENTED("matching.compute_adaptive_min_disp");
}

// ---------------------------------------------------------------------------
// spatial_dedup_frames
//
// Drop frames whose translated bounding box overlaps an already-accepted
// frame by more than `overlap_threshold`.
//
// Returns list of int (keep indices).
// ---------------------------------------------------------------------------
static py::list spatial_dedup_frames(
    py::list frames,
    py::list scans_frames,
    py::list bg_masks,
    py::list image_paths,
    py::list edges,
    float    min_displacement_px)
{
    // TODO (Phase 3): bounding-box overlap check from affines.
    BATCH_NOT_IMPLEMENTED("matching.spatial_dedup_frames");
}

// ---------------------------------------------------------------------------
// register_matching — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_matching(py::module_& m) {
    m.doc() = R"doc(
        batch.matching — Phase correlation and edge graph construction.

        Functions
        ---------
        phase_correlate_masked(frame_a, frame_b, mask_a, mask_b) -> dict
        build_edge_graph(raw_matches, bg_masks, N) -> list[dict]
        reject_static_edges(edges, min_disp_px) -> list[dict]
        compute_adaptive_min_disp(edges) -> float
        spatial_dedup_frames(frames, scans, masks, paths, edges, min_disp) -> list[int]
    )doc";

    m.def("phase_correlate_masked", &phase_correlate_masked,
        py::arg("frame_a_gray"),
        py::arg("frame_b_gray"),
        py::arg("bg_mask_a") = py::none(),
        py::arg("bg_mask_b") = py::none(),
        R"doc(
            Compute phase-correlation shift between two luma frames.

            Args
            ----
            frame_a_gray, frame_b_gray : uint8 (H, W) luma planes
            bg_mask_a, bg_mask_b       : optional uint8 (H, W) fg masks

            Returns
            -------
            dict with keys "dx" (float), "dy" (float), "response" (float [0,1])
        )doc");

    m.def("build_edge_graph", &build_edge_graph,
        py::arg("raw_matches"),
        py::arg("bg_masks"),
        py::arg("N"),
        R"doc(
            Filter raw match dicts through post-match gates and return Edge dicts.

            Gates: §1.36 spread-MAD, §1.38 bg-ratio, §1.47 sign-consistency,
                   §1.48 CV, §1.49 adj-min, §2.14 triangular consistency.

            Args
            ----
            raw_matches : list[dict]  — one entry per frame pair
            bg_masks    : list[ndarray uint8]  — one per frame
            N           : int  — total frame count

            Returns
            -------
            list[dict] with keys "i","j","dx","dy","weight","type"
        )doc");

    m.def("reject_static_edges", &reject_static_edges,
        py::arg("edges"),
        py::arg("min_disp_px") = 50.0f,
        R"doc(
            Drop edges where |dx| < min_disp_px AND |dy| < min_disp_px (§1.2A).

            Returns filtered list[dict].
        )doc");

    m.def("compute_adaptive_min_disp", &compute_adaptive_min_disp,
        py::arg("edges"),
        R"doc(
            Estimate adaptive minimum displacement threshold from edge distribution.

            Returns float (pixels).
        )doc");

    m.def("spatial_dedup_frames", &spatial_dedup_frames,
        py::arg("frames"),
        py::arg("scans_frames"),
        py::arg("bg_masks"),
        py::arg("image_paths"),
        py::arg("edges"),
        py::arg("min_displacement_px"),
        R"doc(
            Drop frames whose translated box overlaps an accepted frame's box.

            Returns list[int] — indices of frames to keep.
        )doc");
}
