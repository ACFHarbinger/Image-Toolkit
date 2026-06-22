// ---------------------------------------------------------------------------
// batch/src/compositing.cpp
//
// Zone normalization chain, Laplacian blend, gain loops, single-pose helpers.
//
// Replaces (compute bodies only — Python wrappers remain):
//   rendering/compositing.py  :: _zone_chroma_align, _zone_lum_norm,
//     _zone_sat_norm, _zone_contrast_eq, _zone_hue_eq, _laplacian_blend,
//     _single_pose_soft_edge, _seam_color_match, _poisson_seam_blend,
//     _smooth_gain_array, _normalize_warped_frames, _blocks_lum_compensate,
//     gain normalization loops, all single-pose escalation gates
//
// Implementation roadmap: Phase 2.
// See moon/roadmaps/asp_cpp_migration.md §batch::compositing
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "batch/common.hpp"
#include "batch/image_utils.hpp"

namespace py = pybind11;

// ---------------------------------------------------------------------------
// zone_chroma_align  (§3.19)
//
// Shift fb's chroma (A*, B* in LAB) to match fa.
// Operates on non-black pixels only (mask from fa luma > 5).
// min_shift_px: minimum mean shift to apply (avoid jitter).
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> zone_chroma_align(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    float                min_shift_px = 2.0f)
{
    // TODO (Phase 2):
    //   cv::cvtColor → LAB; compute mean A*,B* of non-black pixels;
    //   shift = fa_mean - fb_mean (clamped by min_shift_px);
    //   apply per-pixel via forEach<Vec3b>; cvtColor back.
    BATCH_NOT_IMPLEMENTED("compositing.zone_chroma_align");
}

// ---------------------------------------------------------------------------
// zone_lum_norm  (§1.104)
//
// Scale fb's LAB L-channel to match fa's mean luminance.
// gain_clamp: maximum allowed gain ratio.
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> zone_lum_norm(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    float                gain_clamp = 2.0f)
{
    // TODO (Phase 2): LAB L-channel mean ratio, clamped, applied via forEach.
    BATCH_NOT_IMPLEMENTED("compositing.zone_lum_norm");
}

// ---------------------------------------------------------------------------
// zone_sat_norm  (§1.111)
//
// Scale fb's HSV S-channel to match fa's mean saturation.
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> zone_sat_norm(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    float                gain_clamp = 2.0f)
{
    // TODO (Phase 2): HSV S-channel mean ratio, clamped, applied via forEach.
    BATCH_NOT_IMPLEMENTED("compositing.zone_sat_norm");
}

// ---------------------------------------------------------------------------
// zone_contrast_eq  (§1.114)
//
// Scale fb's LAB L-channel standard deviation to match fa's.
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> zone_contrast_eq(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    float                clamp = 2.0f)
{
    // TODO (Phase 2): LAB L std ratio, clamped, applied via forEach.
    BATCH_NOT_IMPLEMENTED("compositing.zone_contrast_eq");
}

// ---------------------------------------------------------------------------
// zone_hue_eq  (§1.127)
//
// Circular mean hue shift from fa to fb (only if |shift| > min_hue_diff_deg).
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> zone_hue_eq(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    float                min_hue_diff_deg = 5.0f)
{
    // TODO (Phase 2): HSV H circular mean diff; apply only if > threshold.
    BATCH_NOT_IMPLEMENTED("compositing.zone_hue_eq");
}

// ---------------------------------------------------------------------------
// laplacian_blend
//
// Multi-band Laplacian pyramid blend guided by a DP seam path.
// Builds a per-pixel soft weight mask from the path (linear ramp ±feather_px).
// Blends n_bands Laplacian pyramid levels, then reconstructs.
//
// Optionally wraps cv::detail::MultiBandBlender (Phase 4: ASP_MULTIBAND_BLEND=1).
//
// Returns uint8 ndarray (H, W, 3) BGR.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> laplacian_blend(
    py::array_t<uint8_t>  fa_zone,
    py::array_t<uint8_t>  fb_zone,
    py::array_t<int32_t>  path,
    int                   feather_px          = 12,
    int                   n_bands             = 5,
    float                 alpha_fine_weight   = 0.3f)
{
    // TODO (Phase 2): build soft weight mask from path; Laplacian pyramid blend.
    // Phase 4 option: cv::detail::MultiBandBlender.
    BATCH_NOT_IMPLEMENTED("compositing.laplacian_blend");
}

// ---------------------------------------------------------------------------
// single_pose_soft_edge
//
// Linear ramp ±soft_px around the DP seam path.
// alpha[y][x] = max(0, 1 - |y - path[x]| / soft_px) × 0.5
// Applied in OpenMP parallel over columns.
//
// Returns blended uint8 ndarray (H, W, 3).
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> single_pose_soft_edge(
    py::array_t<uint8_t> fa_zone,
    py::array_t<uint8_t> fb_zone,
    py::array_t<int32_t> path,
    int                  soft_px = 6)
{
    // TODO (Phase 2): per-column linear ramp blend.
    BATCH_NOT_IMPLEMENTED("compositing.single_pose_soft_edge");
}

// ---------------------------------------------------------------------------
// seam_color_match
//
// Per-channel mean shift in the blend band between dominant and other zone.
//
// Returns uint8 ndarray (H, W, 3) — the corrected other-zone.
// ---------------------------------------------------------------------------
static py::array_t<uint8_t> seam_color_match(
    py::array_t<uint8_t> dom_zone,
    py::array_t<uint8_t> oth_zone,
    py::array_t<int32_t> path,
    int                  band_half_px = 8)
{
    // TODO (Phase 2): compute per-channel mean in band_rows; shift oth_zone.
    BATCH_NOT_IMPLEMENTED("compositing.seam_color_match");
}

// ---------------------------------------------------------------------------
// normalize_warped_frames
//
// Apply per-frame scalar gain corrections with Gaussian smoothing across
// the sequence. Coherence gate (§1.18) skips frames where gain delta > limit.
//
// Returns list of uint8 ndarrays.
// ---------------------------------------------------------------------------
static py::list normalize_warped_frames(
    py::list warped_frames,
    py::list bg_masks,
    int      ref_frame_idx,
    bool     adaptive_gain_clamp = true,
    float    coherence_limit     = 20.0f)
{
    // TODO (Phase 2): per-frame scalar gain with Gaussian smooth + coherence gate.
    BATCH_NOT_IMPLEMENTED("compositing.normalize_warped_frames");
}

// ---------------------------------------------------------------------------
// register_compositing — called from bindings.cpp
// ---------------------------------------------------------------------------
void register_compositing(py::module_& m) {
    m.doc() = R"doc(
        batch.compositing — Zone normalization chain, blending, gain loops.

        Functions
        ---------
        zone_chroma_align(fa, fb, min_shift_px) -> ndarray
        zone_lum_norm(fa, fb, gain_clamp) -> ndarray
        zone_sat_norm(fa, fb, gain_clamp) -> ndarray
        zone_contrast_eq(fa, fb, clamp) -> ndarray
        zone_hue_eq(fa, fb, min_hue_diff_deg) -> ndarray
        laplacian_blend(fa, fb, path, feather_px, n_bands, alpha_fine_weight) -> ndarray
        single_pose_soft_edge(fa, fb, path, soft_px) -> ndarray
        seam_color_match(dom_zone, oth_zone, path, band_half_px) -> ndarray
        normalize_warped_frames(frames, masks, ref, adaptive, coherence_limit) -> list[ndarray]
    )doc";

    m.def("zone_chroma_align", &zone_chroma_align,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("min_shift_px") = 2.0f,
        "§3.19 Chroma shift in LAB A*B* space.");

    m.def("zone_lum_norm", &zone_lum_norm,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("gain_clamp") = 2.0f,
        "§1.104 Luma normalisation via LAB L-channel scalar.");

    m.def("zone_sat_norm", &zone_sat_norm,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("gain_clamp") = 2.0f,
        "§1.111 Saturation normalisation via HSV S-channel scalar.");

    m.def("zone_contrast_eq", &zone_contrast_eq,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("clamp") = 2.0f,
        "§1.114 Contrast equalisation via LAB L std ratio.");

    m.def("zone_hue_eq", &zone_hue_eq,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("min_hue_diff_deg") = 5.0f,
        "§1.127 HSV hue equalisation (circular mean shift, threshold min_hue_diff_deg).");

    m.def("laplacian_blend", &laplacian_blend,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("path"),
        py::arg("feather_px")        = 12,
        py::arg("n_bands")           = 5,
        py::arg("alpha_fine_weight") = 0.3f,
        "Multi-band Laplacian pyramid blend guided by DP seam path.");

    m.def("single_pose_soft_edge", &single_pose_soft_edge,
        py::arg("fa_zone"), py::arg("fb_zone"),
        py::arg("path"),
        py::arg("soft_px") = 6,
        "Linear ramp ±soft_px around DP seam for single-pose escalation.");

    m.def("seam_color_match", &seam_color_match,
        py::arg("dom_zone"), py::arg("oth_zone"),
        py::arg("path"),
        py::arg("band_half_px") = 8,
        "Per-channel mean shift in blend band to reduce seam color discontinuity.");

    m.def("normalize_warped_frames", &normalize_warped_frames,
        py::arg("warped_frames"),
        py::arg("bg_masks"),
        py::arg("ref_frame_idx"),
        py::arg("adaptive_gain_clamp") = true,
        py::arg("coherence_limit")     = 20.0f,
        "Apply per-frame scalar gains with Gaussian smooth + §1.18 coherence gate.");
}
