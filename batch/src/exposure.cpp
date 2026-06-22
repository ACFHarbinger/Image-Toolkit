// ---------------------------------------------------------------------------
// batch/src/exposure.cpp
//
// Block-based gain compensation and vignetting correction.
//
// Replaces:
//   rendering/photometric.py         :: _apply_basic, _correct_vignetting
//   rendering/compositing.py         :: _blocks_gain_compensate,
//                                       _blocks_lum_compensate
//
// Wraps:
//   cv::detail::BlocksGainCompensator   (per-block gain)
//   cv::detail::BlocksChannelsCompensator (per-block per-channel, Phase 4)
//
// Implementation roadmap: Phase 2.
// See moon/roadmaps/asp_cpp_migration.md §batch::exposure
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// blocks_gain_compensate
//
// Wraps cv::detail::BlocksGainCompensator.
// Per 32×32 block: builds overlap matrix A, solve A × gain = b (Eigen Chol),
// apply gain map via bilinear interpolation.
// nr_iterations rounds of 5×5 Gaussian smoothing on the block gain grid.
//
// Args
// ----
// warped_frames : list[ndarray uint8 (H,W,C)]
// warped_masks  : list[ndarray uint8 (H,W)]
// corners       : list[(x,y)] — top-left corner of each frame in canvas
// bl_width, bl_height : block dimensions (pixels)
// nr_feeds      : int — number of compensator feed rounds
// nr_iterations : int — Gaussian smoothing rounds on gain grid
//
// Returns list[ndarray uint8 (H,W,C)] — compensated frames.
// ---------------------------------------------------------------------------
static py::list blocks_gain_compensate(
    py::list warped_frames,
    py::list warped_masks,
    py::list corners,
    int      bl_width     = 32,
    int      bl_height    = 32,
    int      nr_feeds     = 1,
    int      nr_iterations = 2)
{
    // TODO (Phase 2): cv::detail::BlocksGainCompensator.feed().apply() per frame.
    BATCH_NOT_IMPLEMENTED("exposure.blocks_gain_compensate");
}

// ---------------------------------------------------------------------------
// blocks_channels_compensate  (Phase 4: §4.4 white-balance correction)
//
// Wraps cv::detail::BlocksChannelsCompensator.
// Three separate per-block gain maps (B, G, R) for white-balance correction.
//
// Returns list[ndarray uint8 (H,W,C)].
// ---------------------------------------------------------------------------
static py::list blocks_channels_compensate(
    py::list warped_frames,
    py::list warped_masks,
    py::list corners,
    int      bl_width  = 32,
    int      bl_height = 32)
{
    // TODO (Phase 4): cv::detail::BlocksChannelsCompensator.feed().apply().
    BATCH_NOT_IMPLEMENTED("exposure.blocks_channels_compensate");
}

// ---------------------------------------------------------------------------
// correct_vignetting
//
// Apply a pre-computed vignette map (float32, H×W, values in [0,1] where
// 1.0 = no correction) to a single uint8 BGR frame.
//
// Returns uint8 ndarray (H, W, 3).
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> correct_vignetting(
    py::array_t<uint8_t> frame,
    py::array_t<float>   vignette_map)
{
    // TODO (Phase 2): per-pixel multiply + clip-to-255.
    BATCH_NOT_IMPLEMENTED("exposure.correct_vignetting");
}

// ---------------------------------------------------------------------------
// register_exposure — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_exposure(py::module_& m) {
    m.doc() = R"doc(
        batch.exposure — Block gain compensation and vignetting correction.

        Functions
        ---------
        blocks_gain_compensate(frames, masks, corners, bl_w, bl_h, nr_feeds, nr_iters)
            -> list[ndarray]
        blocks_channels_compensate(frames, masks, corners, bl_w, bl_h) -> list[ndarray]
        correct_vignetting(frame, vignette_map) -> ndarray
    )doc";

    m.def("blocks_gain_compensate", &blocks_gain_compensate,
        py::arg("warped_frames"),
        py::arg("warped_masks"),
        py::arg("corners"),
        py::arg("bl_width")      = 32,
        py::arg("bl_height")     = 32,
        py::arg("nr_feeds")      = 1,
        py::arg("nr_iterations") = 2,
        R"doc(
            Per-block gain compensation via cv::detail::BlocksGainCompensator.

            Args
            ----
            warped_frames : list[uint8 ndarray (H,W,C)]
            warped_masks  : list[uint8 ndarray (H,W)]
            corners       : list[(x,y)] top-left canvas corners
            bl_width, bl_height : block size (pixels), default 32×32
            nr_feeds      : compensator feed rounds
            nr_iterations : Gaussian smoothing rounds on gain grid

            Returns list[uint8 ndarray].
        )doc");

    m.def("blocks_channels_compensate", &blocks_channels_compensate,
        py::arg("warped_frames"),
        py::arg("warped_masks"),
        py::arg("corners"),
        py::arg("bl_width")  = 32,
        py::arg("bl_height") = 32,
        R"doc(
            Per-block per-channel (B,G,R) gain for white-balance correction.
            Wraps cv::detail::BlocksChannelsCompensator (Phase 4, §4.4).

            Returns list[uint8 ndarray].
        )doc");

    m.def("correct_vignetting", &correct_vignetting,
        py::arg("frame"),
        py::arg("vignette_map"),
        R"doc(
            Multiply each pixel by vignette_map[y][x] and clip to [0,255].

            Args
            ----
            frame        : uint8 ndarray (H, W, 3) BGR
            vignette_map : float32 ndarray (H, W), values in [0,1]

            Returns uint8 ndarray (H, W, 3).
        )doc");
}
