#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/video/video_batch.hpp
//
// Parallel video thumbnail extraction.
//
// C++ replacement for Rust `base::extract_video_thumbnails_batch`.
// Uses OpenCV VideoCapture + OpenMP; eliminates the Rust ffmpeg subprocess.
//
// Phase 3 of the Rust → C++ migration.
// See moon/roadmaps/rust_to_cpp_migration.md §Phase 3
// ---------------------------------------------------------------------------

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <opencv2/core.hpp>

#include <string>
#include <vector>

namespace py = pybind11;

namespace base::video {

struct VideoThumbResult {
    std::string          path;
    std::vector<cv::Mat> frames;  // one per requested timestamp; empty Mat on seek error
    std::string          error;
};

/// Extract one thumbnail per timestamp from a single video file.
VideoThumbResult extract_thumbnails(
    const std::string&          video_path,
    const std::vector<double>&  timestamps_sec,
    int                         thumb_w = 256,
    int                         thumb_h = 256);

/// Batch version: extracts thumbnails from N videos in parallel (OpenMP).
/// Returns a Python list of (path, [ndarray|None, ...], error_str) tuples.
py::list extract_video_thumbnails_batch(
    const std::vector<std::string>& paths,
    const std::vector<double>&      timestamps_sec,
    int                             thumb_w = 256,
    int                             thumb_h = 256);

} // namespace base::video
