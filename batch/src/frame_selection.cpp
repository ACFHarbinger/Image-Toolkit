// ---------------------------------------------------------------------------
// batch/src/frame_selection.cpp
//
// Classical frame filtering: hold detection, temporal variance, dedup.
//
// Replaces (non-DINOv2 paths):
//   ingestion/frame_selection.py  :: _detect_hold_blocks, _detect_hold_blocks_dhash,
//     _temporal_variance_filter, _near_dup_luma_filter, _smart_select_frames,
//     _spatial_dedup_frames
//
// Implementation roadmap: Phase 5.
// See moon/roadmaps/asp_cpp_migration.md §batch::frame_selection
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// detect_hold_blocks_mad
//
// Per-pair mean absolute difference (MAD) of thumbnail luma planes.
// Returns hold IDs where MAD < threshold.
// OpenMP parallel: each pair (i, i+1) computed independently.
//
// Returns list[int] — frame indices of duplicate (hold) frames.
// ---------------------------------------------------------------------------
static py::list detect_hold_blocks_mad(
    py::list thumbs,
    float    threshold = 0.025f)
{
    // TODO (Phase 5): parallel per-pair MAD on thumbnail luma.
    BATCH_NOT_IMPLEMENTED("frame_selection.detect_hold_blocks_mad");
}

// ---------------------------------------------------------------------------
// detect_hold_blocks_dhash
//
// Perceptual dHash hold detection:
//   1. INTER_AREA resize to (hash_size*2, hash_size) — reduces MPEG DCT noise
//   2. Horizontal gradient binarisation: hash[y][x] = (row[x+1] > row[x]) ? 1 : 0
//   3. Hamming distance via std::bitset XOR popcount
//
// Returns list[int] — hold frame indices where hamming_dist <= hamming_thresh.
// ---------------------------------------------------------------------------
static py::list detect_hold_blocks_dhash(
    py::list thumbs,
    int      hash_size     = 8,
    int      hamming_thresh = 4)
{
    // TODO (Phase 5): INTER_AREA resize + gradient binarise + bitset Hamming.
    BATCH_NOT_IMPLEMENTED("frame_selection.detect_hold_blocks_dhash");
}

// ---------------------------------------------------------------------------
// temporal_variance_filter
//
// For each interior frame i: compute mean per-pixel variance across triplet
// (i-1, i, i+1). Drop if mean variance < sigma_threshold.
// OpenMP parallel per frame.
//
// Returns (filtered_thumbs: list[ndarray], filtered_paths: list[str]).
// ---------------------------------------------------------------------------
static py::tuple temporal_variance_filter(
    py::list thumbs,
    py::list paths,
    float    sigma_threshold = 1e-3f)
{
    // TODO (Phase 5): per-triplet variance, drop below threshold.
    BATCH_NOT_IMPLEMENTED("frame_selection.temporal_variance_filter");
}

// ---------------------------------------------------------------------------
// near_dup_luma_filter
//
// Per-pair mean abs grayscale diff at thumbnail scale.
// Drop near-duplicates (first and last frames are always kept).
//
// Returns (filtered_thumbs: list[ndarray], filtered_paths: list[str]).
// ---------------------------------------------------------------------------
static py::tuple near_dup_luma_filter(
    py::list thumbs,
    py::list paths,
    float    threshold = 3.0f)
{
    // TODO (Phase 5): mean abs luma diff, keep first/last unconditionally.
    BATCH_NOT_IMPLEMENTED("frame_selection.near_dup_luma_filter");
}

// ---------------------------------------------------------------------------
// spatial_dedup_frames  (alias also in matching.cpp — canonical here)
//
// Extract translated bounding boxes from affines.
// Drop frame if its box overlaps an accepted frame's box by > overlap_threshold.
//
// Returns list[int] — indices of frames to keep.
// ---------------------------------------------------------------------------
static py::list spatial_dedup_frames(
    py::list frames,
    py::list scans_frames,
    py::list bg_masks,
    py::list image_paths,
    py::list edges,
    float    min_displacement_px)
{
    // TODO (Phase 5): bounding-box overlap check via affine transforms.
    BATCH_NOT_IMPLEMENTED("frame_selection.spatial_dedup_frames");
}

// ---------------------------------------------------------------------------
// register_frame_selection — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_frame_selection(py::module_& m) {
    m.doc() = R"doc(
        batch.frame_selection — Classical frame filtering.

        Functions
        ---------
        detect_hold_blocks_mad(thumbs, threshold) -> list[int]
        detect_hold_blocks_dhash(thumbs, hash_size, hamming_thresh) -> list[int]
        temporal_variance_filter(thumbs, paths, sigma_threshold) -> (list, list)
        near_dup_luma_filter(thumbs, paths, threshold) -> (list, list)
        spatial_dedup_frames(frames, scans, masks, paths, edges, min_disp) -> list[int]
    )doc";

    m.def("detect_hold_blocks_mad", &detect_hold_blocks_mad,
        py::arg("thumbs"),
        py::arg("threshold") = 0.025f,
        "Detect hold (duplicate) frames via per-pair MAD on thumbnail luma (OpenMP).");

    m.def("detect_hold_blocks_dhash", &detect_hold_blocks_dhash,
        py::arg("thumbs"),
        py::arg("hash_size")      = 8,
        py::arg("hamming_thresh") = 4,
        "Detect hold frames via dHash (INTER_AREA resize + Hamming distance).");

    m.def("temporal_variance_filter", &temporal_variance_filter,
        py::arg("thumbs"),
        py::arg("paths"),
        py::arg("sigma_threshold") = 1e-3f,
        "Drop interior frames with per-triplet variance < sigma_threshold.");

    m.def("near_dup_luma_filter", &near_dup_luma_filter,
        py::arg("thumbs"),
        py::arg("paths"),
        py::arg("threshold") = 3.0f,
        "Drop near-duplicate frames by mean abs luma diff (first/last kept).");

    m.def("spatial_dedup_frames", &spatial_dedup_frames,
        py::arg("frames"),
        py::arg("scans_frames"),
        py::arg("bg_masks"),
        py::arg("image_paths"),
        py::arg("edges"),
        py::arg("min_displacement_px"),
        "Drop frames whose affine-translated bbox overlaps an accepted frame's bbox.");
}
