// ---------------------------------------------------------------------------
// batch/src/canvas.cpp
//
// Warp frames to canvas, per-pixel median render, crop, fill, scroll detect,
// panorama stitch fallback.
//
// Replaces:
//   alignment/canvas.py  :: _compute_canvas, _crop_to_valid, _telea_fill_gaps,
//                           _detect_scroll_axis, _panorama_stitch_fallback
//   rendering/rendering.py :: _render_median, _render, _render_first
//
// Implementation roadmap: Phase 5.
// See moon/roadmaps/asp_cpp_migration.md §batch::canvas
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"
#include "batch/affine_types.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// compute_canvas
//
// Compute bounding box of all warped frame corners.
// Applies midplane shift via bidirectional affine averaging (StabStitch++).
//
// Returns (canvas_h: int, canvas_w: int, shift: (float, float))
// ---------------------------------------------------------------------------
static py::tuple compute_canvas(
    py::list affines,
    py::list frame_shapes)   // list of (H, W) tuples
{
    // TODO (Phase 5): iterate corners of each frame under its affine,
    //   compute bounding box, apply StabStitch++ midplane shift.
    BATCH_NOT_IMPLEMENTED("canvas.compute_canvas");
}

// ---------------------------------------------------------------------------
// warp_frames_to_canvas
//
// Apply cv::warpAffine to all N frames via OpenMP parallel loop.
// Returns list of warped uint8 ndarrays of shape (canvas_h, canvas_w, C).
// ---------------------------------------------------------------------------
static py::list warp_frames_to_canvas(
    py::list frames,
    py::list affines,
    int      canvas_h,
    int      canvas_w)
{
    // TODO (Phase 5): parallel cv::warpAffine with INTER_LINEAR over frames.
    BATCH_NOT_IMPLEMENTED("canvas.warp_frames_to_canvas");
}

// ---------------------------------------------------------------------------
// render_median
//
// Per-pixel nth_element across N warped frames (OpenMP parallel over rows).
// This is the single largest CPU bottleneck in the Python pipeline.
//
// Returns uint8 ndarray (canvas_h, canvas_w, C).
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> render_median(py::list warped_frames)
{
    // TODO (Phase 5): for each pixel, stack N values, nth_element, return median.
    // Overmix::StatisticsRender::MEDIAN pattern.
    BATCH_NOT_IMPLEMENTED("canvas.render_median");
}

// ---------------------------------------------------------------------------
// crop_to_valid
//
// Horizontal scan for valid pixel fraction >= 0.8.
// Returns (y0, y1, x0, x1) bounding rect of valid region.
// ---------------------------------------------------------------------------
static py::tuple crop_to_valid(
    py::array_t<uint8_t> canvas,
    float                valid_fraction = 0.8f)
{
    // TODO (Phase 5): scan rows/cols for valid pixel fraction.
    BATCH_NOT_IMPLEMENTED("canvas.crop_to_valid");
}

// ---------------------------------------------------------------------------
// telea_fill_gaps
//
// Inpaint gap_mask regions using cv::inpaint(INPAINT_TELEA, radius=3).
// Returns filled uint8 ndarray.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> telea_fill_gaps(
    py::array_t<uint8_t> canvas,
    py::array_t<uint8_t> gap_mask,
    int                  inpaint_radius = 3)
{
    // TODO (Phase 5): cv::inpaint(INPAINT_TELEA).
    BATCH_NOT_IMPLEMENTED("canvas.telea_fill_gaps");
}

// ---------------------------------------------------------------------------
// detect_scroll_axis
//
// Compute mean horizontal vs vertical flow from adjacent-frame diffs.
// Returns "vertical" or "horizontal".
// ---------------------------------------------------------------------------
static std::string detect_scroll_axis(py::list frames)
{
    // TODO (Phase 5): compute mean abs row-diff vs col-diff.
    BATCH_NOT_IMPLEMENTED("canvas.detect_scroll_axis");
}

// ---------------------------------------------------------------------------
// panorama_stitch_fallback
//
// Wrap cv::Stitcher_create(PANORAMA) with error-code handling.
// Returns (ok: bool, stitched: ndarray or None).
// ---------------------------------------------------------------------------
static py::tuple panorama_stitch_fallback(py::list frames)
{
    // TODO (Phase 5): cv::Stitcher_create(PANORAMA).stitch(imgs, dst).
    BATCH_NOT_IMPLEMENTED("canvas.panorama_stitch_fallback");
}

// ---------------------------------------------------------------------------
// register_canvas — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_canvas(py::module_& m) {
    m.doc() = R"doc(
        batch.canvas — Warp, crop, fill, and median render.

        Functions
        ---------
        compute_canvas(affines, frame_shapes) -> (int, int, (float,float))
        warp_frames_to_canvas(frames, affines, canvas_h, canvas_w) -> list[ndarray]
        render_median(warped_frames) -> ndarray
        crop_to_valid(canvas, valid_fraction) -> (y0,y1,x0,x1)
        telea_fill_gaps(canvas, gap_mask, inpaint_radius) -> ndarray
        detect_scroll_axis(frames) -> str
        panorama_stitch_fallback(frames) -> (bool, ndarray|None)
    )doc";

    m.def("compute_canvas", &compute_canvas,
        py::arg("affines"),
        py::arg("frame_shapes"),
        "Compute bounding box of all warped frame corners.");

    m.def("warp_frames_to_canvas", &warp_frames_to_canvas,
        py::arg("frames"),
        py::arg("affines"),
        py::arg("canvas_h"),
        py::arg("canvas_w"),
        "Apply cv::warpAffine to all frames in parallel via OpenMP.");

    m.def("render_median", &render_median,
        py::arg("warped_frames"),
        "Per-pixel median render across N warped frames (OpenMP nth_element).");

    m.def("crop_to_valid", &crop_to_valid,
        py::arg("canvas"),
        py::arg("valid_fraction") = 0.8f,
        "Find the largest valid (non-gap) bounding rect in the canvas.");

    m.def("telea_fill_gaps", &telea_fill_gaps,
        py::arg("canvas"),
        py::arg("gap_mask"),
        py::arg("inpaint_radius") = 3,
        "Inpaint gap regions via cv::inpaint(INPAINT_TELEA).");

    m.def("detect_scroll_axis", &detect_scroll_axis,
        py::arg("frames"),
        "Detect whether the dominant scroll direction is horizontal or vertical.");

    m.def("panorama_stitch_fallback", &panorama_stitch_fallback,
        py::arg("frames"),
        "Attempt cv::Stitcher_create(PANORAMA).stitch(); returns (ok, result).");
}
