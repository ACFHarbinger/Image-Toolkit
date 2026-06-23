// ---------------------------------------------------------------------------
// batch/src/matching.cpp
//
// Phase correlation, static edge rejection, adaptive min-disp threshold.
//
// Replaces:
//   flow/cam_flow.py       :: bg_masked_phase_correlate
//   alignment/matching.py  :: _reject_static_edges, _compute_adaptive_min_disp
//   core/pipeline.py       :: _reject_static_edges, _compute_adaptive_min_disp,
//                             _spatial_dedup_frames
//
// Implementation roadmap: Phase 3 (alignment hot path).
// See moon/roadmaps/asp_cpp_migration.md §batch::matching
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/video/tracking.hpp>

#include "batch/common.hpp"
#include "batch/affine_types.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace py = pybind11;

// ---------------------------------------------------------------------------
// Constants (mirror backend/src/constants/animation.py)
// ---------------------------------------------------------------------------
static constexpr float STATIC_EDGE_MIN_DISP_PX  = 50.0f;  // §1.2A
static constexpr float ADAPTIVE_MIN_DISP_FRAC    = 0.10f;  // §1.2C
static constexpr int   CAM_FLOW_MIN_BG_PIXELS    = 500;    // cam_flow.py

// ---------------------------------------------------------------------------
// PhaseResult — return type for phase_correlate_masked_impl
// ---------------------------------------------------------------------------
struct PhaseResult { float dx, dy, response; };

// ---------------------------------------------------------------------------
// phase_correlate_masked_impl (pure C++, callable from Catch2 tests)
//
// Computes sub-pixel camera displacement via cv::phaseCorrelate.  When masks
// are provided, pixels where at least one frame is foreground are zeroed before
// the FFT to restrict correlation to background texture.
//
// mask_a / mask_b : uint8 Mat, nonzero = background.  May be empty.
// Returns {dx, dy, response} matching Python bg_masked_phase_correlate().
// ---------------------------------------------------------------------------
PhaseResult phase_correlate_masked_impl(
    const cv::Mat& fa_gray,
    const cv::Mat& fb_gray,
    const cv::Mat& mask_a,
    const cv::Mat& mask_b)
{
    if (fa_gray.size() != fb_gray.size())
        throw std::invalid_argument(
            "phase_correlate_masked: frame size mismatch");

    // Convert to float32 (cv::phaseCorrelate requires CV_32F or CV_64F)
    cv::Mat fa_f, fb_f;
    fa_gray.convertTo(fa_f, CV_32F);
    fb_gray.convertTo(fb_f, CV_32F);

    // Apply background masking when masks are supplied and large enough
    if (!mask_a.empty() && !mask_b.empty()) {
        cv::Mat bg_a, bg_b, combined_bg, fg;
        cv::compare(mask_a, 0, bg_a, cv::CMP_GT);  // nonzero → background
        cv::compare(mask_b, 0, bg_b, cv::CMP_GT);
        cv::bitwise_and(bg_a, bg_b, combined_bg);   // both-background pixels

        int n_bg = cv::countNonZero(combined_bg);
        if (n_bg >= CAM_FLOW_MIN_BG_PIXELS) {
            cv::bitwise_not(combined_bg, fg);        // foreground: not both-bg
            fa_f.setTo(0.0f, fg);
            fb_f.setTo(0.0f, fg);
        }
    }

    cv::Point2d shift;
    double response = 0.0;
    shift = cv::phaseCorrelate(fa_f, fb_f, cv::Mat(), &response);

    return {static_cast<float>(shift.x),
            static_cast<float>(shift.y),
            static_cast<float>(response)};
}

// ---------------------------------------------------------------------------
// reject_static_edges_impl (pure C++)
//
// §1.2A — Drop edges where |dx| < min_disp_px AND |dy| < min_disp_px.
// Keeps an edge if EITHER axis displacement meets the threshold.
// ---------------------------------------------------------------------------
std::vector<batch::Edge> reject_static_edges_impl(
    const std::vector<batch::Edge>& edges,
    float min_disp_px)
{
    std::vector<batch::Edge> out;
    out.reserve(edges.size());
    for (const auto& e : edges) {
        if (std::abs(e.dx) >= min_disp_px || std::abs(e.dy) >= min_disp_px)
            out.push_back(e);
    }
    return out;
}

// ---------------------------------------------------------------------------
// compute_adaptive_min_disp_impl (pure C++)
//
// §1.2C — Content-adaptive minimum displacement threshold.
// Returns max(STATIC_EDGE_MIN_DISP_PX, ADAPTIVE_MIN_DISP_FRAC × median_step).
// Adjacent edges (dst == src + 1) define the expected inter-frame step.
// ---------------------------------------------------------------------------
float compute_adaptive_min_disp_impl(const std::vector<batch::Edge>& edges)
{
    std::vector<float> adx, ady;
    for (const auto& e : edges) {
        if (e.dst == e.src + 1) {
            adx.push_back(std::abs(e.dx));
            ady.push_back(std::abs(e.dy));
        }
    }

    if (adx.empty())
        return STATIC_EDGE_MIN_DISP_PX;

    auto median_of = [](std::vector<float> v) -> float {
        std::sort(v.begin(), v.end());
        size_t n = v.size();
        return (n % 2 == 0)
            ? (v[n / 2 - 1] + v[n / 2]) * 0.5f
            : v[n / 2];
    };

    float med_x = median_of(adx);
    float med_y = median_of(ady);
    float expected_step = (med_x >= med_y) ? median_of(adx) : median_of(ady);

    return std::max(STATIC_EDGE_MIN_DISP_PX,
                    ADAPTIVE_MIN_DISP_FRAC * expected_step);
}

// ---------------------------------------------------------------------------
// Python bindings
// ---------------------------------------------------------------------------
#ifndef BATCH_TESTS

// ---------------------------------------------------------------------------
// phase_correlate_masked
//
// Python API:
//   result = batch.matching.phase_correlate_masked(frame_a, frame_b)
//   result = batch.matching.phase_correlate_masked(frame_a, frame_b, mask_a, mask_b)
//   # result is a dict with "dx", "dy", "response"
// ---------------------------------------------------------------------------
static py::dict phase_correlate_masked(
    py::array_t<uint8_t> frame_a_gray,
    py::array_t<uint8_t> frame_b_gray,
    py::object           bg_mask_a,
    py::object           bg_mask_b)
{
    cv::Mat fa = batch::mat_from_array(frame_a_gray);
    cv::Mat fb = batch::mat_from_array(frame_b_gray);

    cv::Mat ma, mb;
    if (!bg_mask_a.is_none())
        ma = batch::mat_from_array(bg_mask_a.cast<py::array_t<uint8_t>>());
    if (!bg_mask_b.is_none())
        mb = batch::mat_from_array(bg_mask_b.cast<py::array_t<uint8_t>>());

    auto r = phase_correlate_masked_impl(fa, fb, ma, mb);

    py::dict out;
    out["dx"]       = r.dx;
    out["dy"]       = r.dy;
    out["response"] = r.response;
    return out;
}

// ---------------------------------------------------------------------------
// reject_static_edges — Python wrapper
// ---------------------------------------------------------------------------
static py::list reject_static_edges(py::list edges_py, float min_disp_px)
{
    std::vector<batch::Edge> edges;
    edges.reserve(py::len(edges_py));
    for (auto item : edges_py)
        edges.push_back(batch::edge_from_dict(item.cast<py::dict>()));

    auto filtered = reject_static_edges_impl(edges, min_disp_px);
    return batch::edges_to_list(filtered);
}

// ---------------------------------------------------------------------------
// compute_adaptive_min_disp — Python wrapper
// ---------------------------------------------------------------------------
static float compute_adaptive_min_disp(py::list edges_py)
{
    std::vector<batch::Edge> edges;
    edges.reserve(py::len(edges_py));
    for (auto item : edges_py)
        edges.push_back(batch::edge_from_dict(item.cast<py::dict>()));
    return compute_adaptive_min_disp_impl(edges);
}

// ---------------------------------------------------------------------------
// build_edge_graph — stub (Phase 3 in-progress; complex gate chain)
// ---------------------------------------------------------------------------
static py::list build_edge_graph(py::list, py::list, int)
{
    BATCH_NOT_IMPLEMENTED("matching.build_edge_graph");
}

// ---------------------------------------------------------------------------
// spatial_dedup_frames — stub (Phase 5; bounding-box overlap check)
// ---------------------------------------------------------------------------
static py::list spatial_dedup_frames(py::list, py::list, py::list,
                                     py::list, py::list, float)
{
    BATCH_NOT_IMPLEMENTED("matching.spatial_dedup_frames");
}

// ---------------------------------------------------------------------------
// register_matching — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_matching(py::module_& m) {
    m.doc() = R"doc(
        batch.matching — Phase correlation and edge graph functions.

        Implemented
        -----------
        phase_correlate_masked(frame_a, frame_b, mask_a=None, mask_b=None) -> dict
        reject_static_edges(edges, min_disp_px=50.0) -> list[dict]
        compute_adaptive_min_disp(edges) -> float

        Stubs (Phase 3 / Phase 5)
        -------------------------
        build_edge_graph(raw_matches, bg_masks, N) -> list[dict]
        spatial_dedup_frames(frames, scans, masks, paths, edges, min_disp) -> list[int]
    )doc";

    m.def("phase_correlate_masked", &phase_correlate_masked,
        py::arg("frame_a_gray"),
        py::arg("frame_b_gray"),
        py::arg("bg_mask_a") = py::none(),
        py::arg("bg_mask_b") = py::none(),
        R"doc(
            Compute phase-correlation shift between two luma frames.

            Background pixels (where both masks are nonzero) are used for
            correlation; foreground pixels are zeroed.  Falls back to
            whole-frame correlation when fewer than 500 bg pixels are available.

            Args
            ----
            frame_a_gray, frame_b_gray : uint8 (H, W) luma planes
            bg_mask_a, bg_mask_b       : optional uint8 (H, W) masks,
                                         nonzero = background

            Returns dict with "dx" (float), "dy" (float), "response" (float).
        )doc");

    m.def("reject_static_edges", &reject_static_edges,
        py::arg("edges"),
        py::arg("min_disp_px") = STATIC_EDGE_MIN_DISP_PX,
        R"doc(
            §1.2A — Drop edges where |dx| < min_disp_px AND |dy| < min_disp_px.

            An edge is kept if EITHER axis displacement meets the threshold
            (preserves valid diagonal-scroll edges).

            Returns filtered list[dict].
        )doc");

    m.def("compute_adaptive_min_disp", &compute_adaptive_min_disp,
        py::arg("edges"),
        R"doc(
            §1.2C — Content-adaptive minimum displacement threshold.

            Estimates the expected inter-frame step from adjacent-edge medians
            and returns max(STATIC_EDGE_MIN_DISP_PX, 0.10 × expected_step).

            Returns float (pixels).
        )doc");

    m.def("build_edge_graph", &build_edge_graph,
        py::arg("raw_matches"),
        py::arg("bg_masks"),
        py::arg("N"),
        R"doc(
            Filter raw match dicts through post-match gates (stub — Phase 3).
        )doc");

    m.def("spatial_dedup_frames", &spatial_dedup_frames,
        py::arg("frames"),
        py::arg("scans_frames"),
        py::arg("bg_masks"),
        py::arg("image_paths"),
        py::arg("edges"),
        py::arg("min_displacement_px"),
        R"doc(
            Bounding-box overlap spatial deduplication (stub — Phase 5).
        )doc");
}

#endif // BATCH_TESTS
