#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/image/image_batch.hpp
//
// Parallel image batch loading and thumbnail generation.
//
// C++ replacement for Rust `base::load_image_batch`.
// Uses OpenCV imread + INTER_AREA resize + OpenMP.
//
// Phase 2 of the Rust → C++ migration.
// See moon/roadmaps/rust_to_cpp_migration.md §Phase 2
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <opencv2/core.hpp>

#include <string>
#include <vector>

namespace py = pybind11;

namespace base::image {

struct ImageLoadResult {
    std::string path;
    cv::Mat     thumbnail;   // HxWx3 BGR uint8; empty on error
    std::string error;       // non-empty on error
};

/// Load and thumbnail N images in parallel (OpenMP).
/// Returns a Python list of (path, ndarray|None, error_str) tuples.
py::list load_image_batch(
    const std::vector<std::string>& paths,
    int  thumb_w      = 256,
    int  thumb_h      = 256,
    bool keep_aspect  = true);

} // namespace base::image
