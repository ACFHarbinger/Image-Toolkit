// ---------------------------------------------------------------------------
// batch/src/bindings.cpp
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
// Rust base migration submodules (skeleton — Phases 2–5)
// ---------------------------------------------------------------------------
void register_image(py::module_& m);      // Phase 2: image I/O + filesystem
void register_video(py::module_& m);       // Phase 3: video thumbnails
void register_secret(py::module_& m);       // Phase 4: secure vector database
void register_web(py::module_& m);        // Phase 5: HTTP request sequencing

PYBIND11_MODULE(batch, m) {
    m.doc() = R"doc(
        batch — unified C++ native extension for Image Toolkit.

        Originally the ASP (Anime Stitch Pipeline) accelerated C++ layer;
        now expanding to replace the Rust `base` module entirely.
        See moon/roadmaps/rust_to_cpp_migration.md for the migration plan.

        Animation submodules (complete)
        --------------------------------
        batch.matching        Phase correlation, edge graph, static edge filter
        batch.bundle_adjust   Affine bundle adjustment (GNC-TLS + Eigen LM)
        batch.validation      Affine sequence validation
        batch.canvas          Warp, crop, fill, median render
        batch.seam            Seam DP, cost map, GraphCut seam finder
        batch.compositing     Zone normalisation chain, Laplacian blend, gain
        batch.exposure        BlocksGainCompensator, vignetting correction
        batch.frame_selection Hold detection, temporal filter, dedup
        batch.wave_correct    Linear drift subtraction
        batch.fg_register     ARAP solver, ECC refinement, SLIC-SGM proxy
        batch.sr_classical    DCT restoration, PSO registration, de-seam

        Rust base migration submodules (skeleton)
        ------------------------------------------
        batch.image           load_image_batch, scan_files  (Phase 2)
        batch.video           extract_video_thumbnails_batch  (Phase 3)
        batch.secret          insert/search/fetch/delete secure listings  (Phase 4)
        batch.web             run_web_requests_sequence  (Phase 5)
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
    // Rust base migration submodules
    // ------------------------------------------------------------------
    auto m_images    = m.def_submodule("image",
        "Parallel image batch loading, thumbnail generation, filesystem scan. "
        "(Phase 2 — replaces Rust load_image_batch / scan_files)");
    auto m_video     = m.def_submodule("video",
        "Parallel video thumbnail extraction via OpenCV VideoCapture. "
        "(Phase 3 — replaces Rust extract_video_thumbnails_batch)");
    auto m_vault     = m.def_submodule("secret",
        "Encrypted vector database: Argon2id KDF, SQLCipher, sqlite-vec, Arrow export. "
        "(Phase 4 — replaces Rust secure_vector_db)");
    auto m_http      = m.def_submodule("web",
        "HTTP request sequencing with JSON config and progress callbacks. "
        "(Phase 5 — replaces Rust run_web_requests_sequence)");

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
