// ---------------------------------------------------------------------------
// batch/src/seam.cpp
//
// Seam finding: DP (_seam_cut), cost map builder, GraphCut seam finder,
// parallel seam batch.
//
// Replaces (hot path — ~40% of total pipeline time):
//   rendering/compositing.py  :: _seam_cut, _build_seam_cost_map,
//                                _find_optimal_boundaries
//
// New algorithms (Phase 4):
//   cv::detail::GraphCutSeamFinder — global multi-image seam
//   OpenMP seam_batch              — parallel N-1 seams
//
// Implementation roadmap: Phase 2 (seam DP + cost map) + Phase 4 (GraphCut).
// See moon/roadmaps/asp_cpp_migration.md §batch::seam
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"
#include "batch/affine_types.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// seam_cut
//
// Forward-DP seam finder operating column-wise on two overlapping zone crops.
//
// Energy per pixel:
//   E[y][x] = diff + 0.5*|∇diff| + edge_weight*(|∇img1|+|∇img2|) + sem_cost
//   plus optional §1.125 midline transition penalty.
//
// DP forward pass:
//   dp[y][x] = E[y][x] + min(dp[y-1][x-1], dp[y][x-1], dp[y+1][x-1])
//
// Traceback: column-wise argmin.
//
// Returns list[int] of length W (seam row per column).
// ---------------------------------------------------------------------------
static py::array_t<int32_t> seam_cut(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    py::object           sem_cost           = py::none(),  // float32 (H,W) or None
    py::object           waypoints          = py::none(),  // list[int] or None
    float                transition_penalty = 0.0f,
    float                edge_weight        = 1.0f)
{
    // TODO (Phase 2): implement DP seam finder.
    // See roadmap §batch::seam for the full C++ pseudocode.
    BATCH_NOT_IMPLEMENTED("seam.seam_cut");
}

// ---------------------------------------------------------------------------
// build_seam_cost_map
//
// Six-tier cost map from foreground masks:
//   Tier 0:   background         = 0.0
//   Tier 0.3: outer fg ring      = 0.3  (§3.20 EXTRA_FG_DILATION)
//   Tier 0.5: edge buffer        = 0.5  (§3.Tier-2 buffer)
//   Tier 1.0: fg interior        = 1.0
//   Tier 1.5: fg-heavy columns   = 1.5  (§1.126 FG_MAJORITY_FLOOR)
//   Tier 2.0: dominated columns  = 2.0  (§3.15A column barrier)
//   Tier 1e6: pinned rows        (hard barrier)
//
// Additional modifiers:
//   §1.110 COST_MAP_BLUR_SIGMA  : cv::GaussianBlur on soft cost
//   §1.113 COST_COL_SMOOTH_SIGMA: 1D Gaussian on per-column mean
//   §1.109 COST_MAP_NORM        : renormalize barriers after blur
//   §1.123 SCATTER_COST         : local 3×3 variance via cv::boxFilter
//
// Returns float32 ndarray (H, W).
// ---------------------------------------------------------------------------
static py::array_t<float> build_seam_cost_map(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> bg_mask_a,
    py::array_t<uint8_t> bg_mask_b,
    float                cost_map_blur_sigma   = 0.0f,
    float                cost_col_smooth_sigma = 0.0f,
    bool                 cost_map_norm         = true,
    float                scatter_cost_weight   = 0.0f,
    py::object           pinned_rows           = py::none())
{
    // TODO (Phase 2): implement six-tier cost map with all modifiers.
    BATCH_NOT_IMPLEMENTED("seam.build_seam_cost_map");
}

// ---------------------------------------------------------------------------
// graphcut_seam_find  (Phase 4)
//
// Wraps cv::detail::GraphCutSeamFinder("COST_COLOR_GRAD").
// Global multi-image seam optimisation — eliminates pairwise DP conflicts.
//
// Args
// ----
// warped_frames : list[ndarray uint8 (H,W,C)] — N frames in canvas space
// warped_masks  : list[ndarray uint8 (H,W)]   — N binary masks
// corners       : list[(x,y)]                 — top-left corner per frame
//
// Returns list[ndarray uint8 (H,W)] — N updated ownership masks
// ---------------------------------------------------------------------------
static py::list graphcut_seam_find(
    py::list warped_frames,
    py::list warped_masks,
    py::list corners)
{
    // TODO (Phase 4): cv::detail::GraphCutSeamFinder.find(imgs, pts, masks).
    BATCH_NOT_IMPLEMENTED("seam.graphcut_seam_find");
}

// ---------------------------------------------------------------------------
// seam_batch
//
// Compute N-1 seams in parallel via OpenMP.
// Each ZonePair provides (fa, fb, cost) for one adjacent pair.
// GIL is released during the OpenMP parallel region.
//
// Returns list[ndarray int32 (W,)] — one seam path per pair.
// ---------------------------------------------------------------------------
static py::list seam_batch(
    py::list zone_pairs,         // list of dicts with "fa","fb","cost"
    float    edge_weight         = 1.0f,
    float    transition_penalty  = 0.0f)
{
    // TODO (Phase 2):
    //   py::gil_scoped_release release;
    //   #pragma omp parallel for schedule(dynamic)
    //   ... call seam_cut_impl per pair ...
    BATCH_NOT_IMPLEMENTED("seam.seam_batch");
}

// ---------------------------------------------------------------------------
// register_seam — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_seam(py::module_& m) {
    m.doc() = R"doc(
        batch.seam — Seam DP, cost map, GraphCut seam, parallel batch.

        Functions
        ---------
        seam_cut(fa_zone, fb_zone, sem_cost, waypoints, transition_penalty, edge_weight)
            -> ndarray[int32, shape=(W,)]
        build_seam_cost_map(fa_zone, bg_mask_a, bg_mask_b, ...) -> ndarray[float32]
        graphcut_seam_find(warped_frames, warped_masks, corners) -> list[ndarray]
        seam_batch(zone_pairs, edge_weight, transition_penalty) -> list[ndarray]
    )doc";

    m.def("seam_cut", &seam_cut,
        py::arg("fa_zone"),
        py::arg("fb_zone"),
        py::arg("sem_cost")           = py::none(),
        py::arg("waypoints")          = py::none(),
        py::arg("transition_penalty") = 0.0f,
        py::arg("edge_weight")        = 1.0f,
        R"doc(
            Column-wise DP seam cutter.

            Energy E[y][x] = |diff| + 0.5*|∇diff| + edge_w*(|∇img1|+|∇img2|)
                           + sem_cost + transition_penalty * dist_from_midline.
            DP: dp[y][x] = E[y][x] + min(dp[y±1][x-1], dp[y][x-1]).

            Args
            ----
            fa_zone, fb_zone      : uint8 (H, W, 3) BGR zone crops
            sem_cost              : float32 (H, W) or None
            waypoints             : list[int] y-pin rows or None
            transition_penalty    : float ≥ 0 — §1.125 midline prior weight
            edge_weight           : float — image gradient weight

            Returns
            -------
            int32 ndarray of shape (W,) — seam row index per column
        )doc");

    m.def("build_seam_cost_map", &build_seam_cost_map,
        py::arg("fa_zone"),
        py::arg("bg_mask_a"),
        py::arg("bg_mask_b"),
        py::arg("cost_map_blur_sigma")   = 0.0f,
        py::arg("cost_col_smooth_sigma") = 0.0f,
        py::arg("cost_map_norm")         = true,
        py::arg("scatter_cost_weight")   = 0.0f,
        py::arg("pinned_rows")           = py::none(),
        R"doc(
            Build a six-tier seam cost map from foreground masks.

            Tiers: 0.0 (bg), 0.3 (outer ring), 0.5 (buffer), 1.0 (fg),
                   1.5 (fg-heavy columns), 2.0 (dominated columns), 1e6 (hard barrier).

            Returns float32 ndarray (H, W).
        )doc");

    m.def("graphcut_seam_find", &graphcut_seam_find,
        py::arg("warped_frames"),
        py::arg("warped_masks"),
        py::arg("corners"),
        R"doc(
            Global multi-image seam via cv::detail::GraphCutSeamFinder.

            Input: N frames + N masks + N (x,y) corners in canvas space.
            Output: N updated ownership masks (255 = owned by this frame).

            Gate: ASP_GRAPHCUT_SEAM=1 in Python wrapper (Phase 4).
        )doc");

    m.def("seam_batch", &seam_batch,
        py::arg("zone_pairs"),
        py::arg("edge_weight")        = 1.0f,
        py::arg("transition_penalty") = 0.0f,
        R"doc(
            Compute N-1 seam paths in parallel via OpenMP (GIL released).

            Args
            ----
            zone_pairs : list[dict] each with keys "fa","fb","cost"
            edge_weight, transition_penalty : forwarded to seam_cut

            Returns list[ndarray int32 (W,)].
        )doc");
}
