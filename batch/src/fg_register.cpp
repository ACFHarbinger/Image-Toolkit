// ---------------------------------------------------------------------------
// batch/src/fg_register.cpp
//
// ARAP foreground registration: SLIC-SGM proxy, LSD collinearity,
// ARAP sparse solver, ECC affine refinement.
//
// Replaces (non-flow-inference parts):
//   alignment/fg_register.py  :: _slic_sgm_proxy, _arap_regularise, LSD collinearity
//   alignment/ecc.py          :: _ecc_refine
//
// Dependencies:
//   Required : OpenCV imgproc, video, Eigen3
//   Optional : OpenCV ximgproc (SLIC) — guarded with HAVE_OPENCV_XIMGPROC
//
// Implementation roadmap: Phase 5.
// See moon/roadmaps/asp_cpp_migration.md §batch::fg_register
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// slic_sgm_proxy
//
// SLIC superpixel segmentation + flow consensus (SGM proxy):
//   cv::ximgproc::createSuperpixelSLIC(SLICO, region_size, ruler).iterate(10)
//   For each SLIC segment, compute mean flow from SEA-RAFT output.
//   Returns per-pixel "consensus flow" where SLIC smooths noisy optical flow.
//
// Only compiled when HAVE_OPENCV_XIMGPROC is defined.
// Falls back to Python implementation if ximgproc not available at compile time.
//
// Args
// ----
// image    : uint8 (H, W, 3) BGR
// raw_flow : float32 (H, W, 2) — (dx, dy) from SEA-RAFT
// region_size : int — SLIC region size
//
// Returns float32 ndarray (H, W, 2).
// ---------------------------------------------------------------------------
static py::array_t<float> slic_sgm_proxy(
    py::array_t<uint8_t> image,
    py::array_t<float>   raw_flow,
    int                  region_size = 10)
{
    // TODO (Phase 5): SLIC superpixel + per-segment flow mean.
    // Guard with #ifdef HAVE_OPENCV_XIMGPROC.
    BATCH_NOT_IMPLEMENTED("fg_register.slic_sgm_proxy");
}

// ---------------------------------------------------------------------------
// lsd_collinearity
//
// Detect line segments in seam_band_crop via cv::createLineSegmentDetector.
// Project flow component along each line direction.
// Constraint: u_proj ≈ 0 for vertical lines.
// Returns sparse linear constraints for ARAP regularization.
//
// Args
// ----
// seam_band_crop : uint8 (H_band, W_band, 3)
// image_offset   : (y0, x0) — converts LSD coordinates to canvas space
//
// Returns list[dict] with keys "row","col","weight","direction".
// ---------------------------------------------------------------------------
static py::list lsd_collinearity(
    py::array_t<uint8_t> seam_band_crop,
    py::tuple            image_offset)
{
    // TODO (Phase 5): cv::createLineSegmentDetector.detect() + project flow.
    BATCH_NOT_IMPLEMENTED("fg_register.lsd_collinearity");
}

// ---------------------------------------------------------------------------
// arap_push_regularise
//
// ARAP (As-Rigid-As-Possible) regularisation via sparse Eigen solver.
// Builds sparse system from flow constraints + LSD collinearity constraints.
// Solves via Eigen::SparseLU or Eigen::ConjugateGradient.
//
// 10–20× faster than scipy.sparse.linalg.spsolve for matrices under 10k cells.
//
// Args
// ----
// fg_zone         : uint8 (H, W, 3)
// flow            : float32 (H, W, 2)
// lsd_constraints : list[dict] — from lsd_collinearity
//
// Returns uint8 ndarray (H, W, 3) — warped foreground zone.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> arap_push_regularise(
    py::array_t<uint8_t> fg_zone,
    py::array_t<float>   flow,
    py::list             lsd_constraints)
{
    // TODO (Phase 5): build sparse Eigen system; SparseLU/CG solve; warp.
    BATCH_NOT_IMPLEMENTED("fg_register.arap_push_regularise");
}

// ---------------------------------------------------------------------------
// ecc_refine
//
// ECC affine refinement via cv::findTransformECC.
// Python wrapper eliminates Mat↔ndarray copies around the cv2 call.
//
// Args
// ----
// template_frame : uint8 (H, W) or (H, W, 3) — reference
// source_frame   : uint8 (H, W) or (H, W, 3) — frame to align
// initial_M      : float64 ndarray (2, 3)     — initial affine matrix
// mask           : uint8 (H, W) or None
// motion_type    : int — cv::MOTION_EUCLIDEAN (default) or MOTION_AFFINE
// max_iters      : int — ECC iteration limit
// eps            : float — convergence threshold
//
// Returns float64 ndarray (2, 3) — refined affine matrix.
// ---------------------------------------------------------------------------
static py::array_t<double> ecc_refine(
    py::array_t<uint8_t> template_frame,
    py::array_t<uint8_t> source_frame,
    py::array_t<double>  initial_M,
    py::object           mask        = py::none(),
    int                  motion_type = 4,   // cv::MOTION_EUCLIDEAN
    int                  max_iters   = 50,
    double               eps         = 1e-3)
{
    // TODO (Phase 5): cv::findTransformECC(tmpl, src, M, motion_type, criteria, mask).
    BATCH_NOT_IMPLEMENTED("fg_register.ecc_refine");
}

// ---------------------------------------------------------------------------
// register_fg_register — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_fg_register(py::module_& m) {
    m.doc() = R"doc(
        batch.fg_register — ARAP foreground registration (non-flow parts).

        The flow inference (SEA-RAFT, DISOpticalFlow) stays in Python.
        C++ accelerates SLIC-SGM proxy, LSD collinearity, ARAP sparse solver,
        and ECC affine refinement.

        Functions
        ---------
        slic_sgm_proxy(image, raw_flow, region_size) -> ndarray float32 (H,W,2)
        lsd_collinearity(seam_band_crop, image_offset) -> list[dict]
        arap_push_regularise(fg_zone, flow, lsd_constraints) -> ndarray uint8
        ecc_refine(template, source, initial_M, mask, motion_type, max_iters, eps)
            -> ndarray float64 (2,3)
    )doc";

    m.def("slic_sgm_proxy", &slic_sgm_proxy,
        py::arg("image"),
        py::arg("raw_flow"),
        py::arg("region_size") = 10,
        R"doc(
            SLIC superpixel + per-segment flow mean (SGM proxy).

            Requires OpenCV ximgproc (SLIC) at compile time.
            Falls back to Python implementation if unavailable.

            Returns float32 (H, W, 2) consensus flow.
        )doc");

    m.def("lsd_collinearity", &lsd_collinearity,
        py::arg("seam_band_crop"),
        py::arg("image_offset"),
        R"doc(
            Detect LSD line segments and build collinearity constraints for ARAP.

            Returns list[dict] with keys "row","col","weight","direction".
        )doc");

    m.def("arap_push_regularise", &arap_push_regularise,
        py::arg("fg_zone"),
        py::arg("flow"),
        py::arg("lsd_constraints"),
        R"doc(
            ARAP foreground warp via Eigen SparseLU (10–20× faster than scipy).

            Returns warped uint8 (H, W, 3) foreground zone.
        )doc");

    m.def("ecc_refine", &ecc_refine,
        py::arg("template_frame"),
        py::arg("source_frame"),
        py::arg("initial_M"),
        py::arg("mask")        = py::none(),
        py::arg("motion_type") = 4,   // cv::MOTION_EUCLIDEAN
        py::arg("max_iters")   = 50,
        py::arg("eps")         = 1e-3,
        R"doc(
            ECC affine refinement via cv::findTransformECC.

            Returns refined float64 (2, 3) affine matrix.
        )doc");
}
