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
void register_fg_register(py::module_& m);

// ---------------------------------------------------------------------------
// Native base submodules (Phases 2–5, complete)
// ---------------------------------------------------------------------------
void register_image(py::module_& m);      // Phase 2: image I/O + filesystem
void register_video(py::module_& m);      // Phase 3: video thumbnails
void register_secret(py::module_& m);     // Phase 4: secure vector database
void register_database(py::module_& m);   // Phase DB: unified library database
void register_web(py::module_& m);        // Phase 5+9: HTTP + board crawlers + cloud sync

// ---------------------------------------------------------------------------
// Phases 8–11: core, utils, math
// ---------------------------------------------------------------------------
namespace base::core {
    void register_convert(py::module_& m);    // Phase 8: image/video conversion
    void register_filesystem(py::module_& m); // Phase 8: filesystem utils
    void register_finder(py::module_& m);     // Phase 8: duplicate/similar image finder
    void register_merger(py::module_& m);     // Phase 8: image canvas merging
    void register_wallpaper(py::module_& m);  // Phase 8: wallpaper (gnome/kde)
}
namespace base::similarity {
    void register_similarity(py::module_& m);  // Similarity Finder detection engine
}
namespace base::recon {
    void register_recon(py::module_& m);       // Entity Recon identity index + hashing
}
namespace base::roi {
    void register_roi(py::module_& m);         // Reverse-search ROI crop + auto-crop
}
namespace base::utils {
    void register_migration(py::module_& m);         // Phase 10: legacy JSON→SQLCipher migration
    void register_slideshow(py::module_& m);          // Phase 10: background slideshow daemon
    void register_monitor_slideshow(py::module_& m);  // per-monitor graph slideshow scheduler
}
void register_math(py::module_& m);       // Phase 11: distance/stats/info/graph/linalg/dim_reduce

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
        base.fg_register     ARAP solver, ECC refinement, SLIC-SGM proxy

        Native base submodules (Phase 2–5)
        ------------------------------------
        base.image           load_image_batch, scan_files
        base.video           extract_video_thumbnails_batch
        base.secret          insert/search/fetch/delete secure listings
        base.web             run_web_requests_sequence, run_board_crawler, run_sync,
                             run_reverse_image_search (stub), run_image_crawler (stub)

        Phase 8–11 submodules
        ----------------------
        base.core            convert_single_image, convert_image_batch, convert_video,
                             get_files_by_extension, delete_files_by_extensions, delete_path,
                             find_duplicate_images, find_similar_images_phash,
                             merge_images_horizontal, merge_images_vertical, merge_images_grid,
                             set_wallpaper_gnome, evaluate_kde_script
        base.utils           run_legacy_migration, run_slideshow_daemon, run_monitor_slideshow
        base.math            distance.*, stats.*, information.*, graph.*, linalg.pca,
                             dim_reduce.mds, dim_reduce.tsne_affinities
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
    auto m_fgreg     = m.def_submodule("fg_register",
        "ARAP Push+Regularise sparse solver, ECC refinement.");

    // ------------------------------------------------------------------
    // Native base submodules
    // ------------------------------------------------------------------
    auto m_images    = m.def_submodule("image",
        "Parallel image batch loading, thumbnail generation, filesystem scan.");
    auto m_video     = m.def_submodule("video",
        "Parallel video thumbnail extraction via OpenCV VideoCapture.");
    auto m_vault     = m.def_submodule("secret",
        "Encrypted vector database: Argon2id KDF, SQLCipher, cosine search, Arrow export.");
    auto m_database  = m.def_submodule("database",
        "Unified Library Database: session-keyed SQLCipher engine (Phase DB). "
        "Argon2id once per Database instance; generic SQL primitives + knn.");
    auto m_http      = m.def_submodule("web",
        "HTTP request sequencing with JSON config and progress callbacks.");

    // Phase 8–11 submodules
    auto m_core      = m.def_submodule("core",
        "Image/video conversion, filesystem ops, duplicate finder, canvas merger, wallpaper.");
    auto m_sim       = m.def_submodule("similarity",
        "Similarity Finder: xxHash64, pHash/dHash/wHash consensus, VP-tree, HNSW, "
        "SSIM, ORB/SIFT geometric verification, difference masks.");
    auto m_recon     = m.def_submodule("recon",
        "Entity Recon: HNSW identity index (embedding→FirstName_LastName) and "
        "alpha-cutout hashing for provenance caching.");
    auto m_roi       = m.def_submodule("roi",
        "Reverse-search ROI preprocessing: pixel-space crop + saliency auto-crop.");
    auto m_utils     = m.def_submodule("utils",
        "Legacy JSON→SQLCipher migration and background slideshow daemon.");
    auto m_math      = m.def_submodule("math",
        "Math utilities: distance, stats, information, graph, linalg (PCA), dim_reduce (MDS/t-SNE).");

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
    register_fg_register(m_fgreg);

    register_image(m_images);
    register_video(m_video);
    register_secret(m_vault);
    register_database(m_database);
    register_web(m_http);

    // Phase 8: core
    base::core::register_convert(m_core);
    base::core::register_filesystem(m_core);
    base::core::register_finder(m_core);
    base::core::register_merger(m_core);
    base::core::register_wallpaper(m_core);

    // Similarity Finder engine
    base::similarity::register_similarity(m_sim);

    // Entity Recon data/discovery engine
    base::recon::register_recon(m_recon);

    // Reverse-search ROI preprocessing
    base::roi::register_roi(m_roi);

    // Phase 10: utils
    base::utils::register_migration(m_utils);
    base::utils::register_slideshow(m_utils);
    base::utils::register_monitor_slideshow(m_utils);

    // Phase 11: math
    register_math(m_math);

    // ------------------------------------------------------------------
    // Backwards Compatibility: Export methods directly to root module
    // ------------------------------------------------------------------
    m.attr("load_image_batch")               = m_images.attr("load_image_batch");
    m.attr("scan_files")                     = m_images.attr("scan_files");
    m.attr("scan_files_single")              = m_images.attr("scan_files_single");
    // Alias multi to the standard scan_files for backwards compatibility
    m.attr("scan_files_multi")               = m_images.attr("scan_files");
    
    m.attr("extract_video_thumbnails_batch") = m_video.attr("extract_video_thumbnails_batch");
    
    m.attr("insert_listing_secure")          = m_vault.attr("insert_listing_secure");
    m.attr("hybrid_search_secure")           = m_vault.attr("hybrid_search_secure");
    m.attr("fetch_all_listings_secure")      = m_vault.attr("fetch_all_listings_secure");
    m.attr("delete_listing_secure")          = m_vault.attr("delete_listing_secure");
    m.attr("fetch_listings_as_arrow_pointers") = m_vault.attr("fetch_listings_as_arrow_pointers");
    
    m.attr("run_web_requests_sequence")      = m_http.attr("run_web_requests_sequence");
    m.attr("run_board_crawler")              = m_http.attr("run_board_crawler");
    m.attr("run_sync")                       = m_http.attr("run_sync");
    m.attr("run_reverse_image_search")       = m_http.attr("run_reverse_image_search");
    m.attr("run_image_crawler")              = m_http.attr("run_image_crawler");
    
    m.attr("convert_single_image")           = m_core.attr("convert_single_image");
    m.attr("convert_image_batch")            = m_core.attr("convert_image_batch");
    m.attr("convert_video")                  = m_core.attr("convert_video");
    m.attr("get_files_by_extension")         = m_core.attr("get_files_by_extension");
    m.attr("delete_files_by_extensions")     = m_core.attr("delete_files_by_extensions");
    m.attr("delete_path")                    = m_core.attr("delete_path");
    m.attr("find_duplicate_images")          = m_core.attr("find_duplicate_images");
    m.attr("find_similar_images_phash")      = m_core.attr("find_similar_images_phash");
    m.attr("merge_images_horizontal")        = m_core.attr("merge_images_horizontal");
    m.attr("merge_images_vertical")          = m_core.attr("merge_images_vertical");
    m.attr("merge_images_grid")              = m_core.attr("merge_images_grid");
    m.attr("set_wallpaper_gnome")            = m_core.attr("set_wallpaper_gnome");
    m.attr("evaluate_kde_script")            = m_core.attr("evaluate_kde_script");
    
    m.attr("run_legacy_migration")           = m_utils.attr("run_legacy_migration");
    m.attr("run_slideshow_daemon")           = m_utils.attr("run_slideshow_daemon");
    m.attr("run_monitor_slideshow")          = m_utils.attr("run_monitor_slideshow");
}
