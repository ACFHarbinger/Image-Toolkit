// ---------------------------------------------------------------------------
// base/src/bindings.cpp
//
// pybind11 module root — registers all submodules.
//
// Each submodule lives in its own .cpp file and exposes a single
// register_*(py::module_&) function that wires its API.
//
// Adding a new submodule:
//   1. Add a register_xxx(py::module_&) forward declaration here.
//   2. Add `auto m_xxx = m.def_submodule("xxx")` below.
//   3. Call `register_xxx(m_xxx)`.
//   4. Add xxx.cpp to CMakeLists.txt.
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>

namespace py = pybind11;

// ---------------------------------------------------------------------------
// Animation / Anime Stitch Pipeline submodules (complete — all 6 phases)
// ---------------------------------------------------------------------------
void register_matching(py::module_& m);
void register_bundle_adjust(py::module_& m);
void register_validation(py::module_& m);
void register_canvas(py::module_& m);
void register_seam(py::module_& m);
void register_compositing(py::module_& m);
void register_exposure(py::module_& m);
void register_frame_selection(py::module_& m);
void register_wave_correct(py::module_& m);
void register_fg_register(py::module_& m);
void register_sr_classical(py::module_& m);

// ---------------------------------------------------------------------------
// Native base submodules (Phases 2–5, complete)
// ---------------------------------------------------------------------------
void register_image(py::module_& m);      // Phase 2: image I/O + filesystem
void register_video(py::module_& m);      // Phase 3: video thumbnails
void register_secret(py::module_& m);     // Phase 4: secure vector database
void register_web(py::module_& m);        // Phase 5: HTTP request sequencing

PYBIND11_MODULE(base, m) {
    m.doc() = R"doc(
        base — unified C++ native extension for Image Toolkit.

        Replaces the former Rust PyO3 base module. Originally the ASP
        (Anime Stitch Pipeline) accelerated C++ layer (batch/), now the
        single native extension for all image processing, animation pipeline,
        secure storage, and HTTP sequencing functionality.

        Animation submodules (complete)
        --------------------------------
        base.matching        Phase correlation, edge graph, static edge filter
        base.bundle_adjust   Affine bundle adjustment (GNC-TLS + Eigen LM)
        base.validation      Affine sequence validation
        base.canvas          Warp, crop, fill, median render
        base.seam            Seam DP, cost map, GraphCut seam finder
        base.compositing     Zone normalisation chain, Laplacian blend, gain
        base.exposure        BlocksGainCompensator, vignetting correction
        base.frame_selection Hold detection, temporal filter, dedup
        base.wave_correct    Linear drift subtraction
        base.fg_register     ARAP solver, ECC refinement, SLIC-SGM proxy
        base.sr_classical    DCT restoration, PSO registration, de-seam

        Native base submodules (Phase 2–5)
        ------------------------------------
        base.image           load_image_batch, scan_files
        base.video           extract_video_thumbnails_batch
        base.secret          insert/search/fetch/delete secure listings
        base.web             run_web_requests_sequence
    )doc";

    // ------------------------------------------------------------------
    // Animation submodules
    // ------------------------------------------------------------------
    auto m_matching  = m.def_submodule("matching",
        "Phase correlation, edge graph construction and static edge filtering.");
    auto m_ba        = m.def_submodule("bundle_adjust",
        "Affine bundle adjustment: GNC-TLS outer loop, Eigen LM inner solve.");
    auto m_valid     = m.def_submodule("validation",
        "Affine sequence validation (monotone step, ratio, gap checks).");
    auto m_canvas    = m.def_submodule("canvas",
        "Warp frames to canvas, per-pixel median render, crop, fill, scroll detect.");
    auto m_seam      = m.def_submodule("seam",
        "Seam DP (_seam_cut), cost map, GraphCut seam finder, parallel seam batch.");
    auto m_comp      = m.def_submodule("compositing",
        "Zone normalisation chain, Laplacian blend, gain loops.");
    auto m_exp       = m.def_submodule("exposure",
        "BlocksGainCompensator, ChannelsCompensator, vignetting correction.");
    auto m_fsel      = m.def_submodule("frame_selection",
        "Hold detection (MAD + dHash), temporal variance, near-dup, spatial dedup.");
    auto m_wave      = m.def_submodule("wave_correct",
        "Linear drift subtraction via least-squares polyfit.");
    auto m_fgreg     = m.def_submodule("fg_register",
        "SLIC-SGM proxy, LSD collinearity, ARAP sparse solver, ECC refinement.");
    auto m_sr        = m.def_submodule("sr_classical",
        "DCT restoration, PSO sub-pixel registration, de-seam, Overmix L1 SR.");

    // ------------------------------------------------------------------
    // Native base submodules
    // ------------------------------------------------------------------
    auto m_images    = m.def_submodule("image",
        "Parallel image batch loading, thumbnail generation, filesystem scan.");
    auto m_video     = m.def_submodule("video",
        "Parallel video thumbnail extraction via OpenCV VideoCapture.");
    auto m_vault     = m.def_submodule("secret",
        "Encrypted vector database: Argon2id KDF, SQLCipher, cosine search, Arrow export.");
    auto m_http      = m.def_submodule("web",
        "HTTP request sequencing with JSON config and progress callbacks.");

    // ------------------------------------------------------------------
    // Register all submodule APIs
    // ------------------------------------------------------------------
    register_matching(m_matching);
    register_bundle_adjust(m_ba);
    register_validation(m_valid);
    register_canvas(m_canvas);
    register_seam(m_seam);
    register_compositing(m_comp);
    register_exposure(m_exp);
    register_frame_selection(m_fsel);
    register_wave_correct(m_wave);
    register_fg_register(m_fgreg);
    register_sr_classical(m_sr);

    register_image(m_images);
    register_video(m_video);
    register_secret(m_vault);
    register_web(m_http);
}
