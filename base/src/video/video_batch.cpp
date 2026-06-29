// ---------------------------------------------------------------------------
// batch/src/video/video_batch.cpp
//
// Parallel video thumbnail extraction.
//
// C++ replacement for Rust `base::extract_video_thumbnails_batch`.
// Uses OpenCV VideoCapture + OpenMP; eliminates the Rust ffmpeg subprocess.
//
// Implementation: Phase 3 of the Rust → C++ migration.
// See moon/roadmaps/rust_to_cpp_migration.md §Phase 3
// ---------------------------------------------------------------------------

#include "video/video_batch.hpp"
#include "common.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

#include <omp.h>

namespace py = pybind11;

namespace base::video {

VideoThumbResult extract_thumbnails(
    const std::string&         video_path,
    const std::vector<double>& timestamps_sec,
    int                        thumb_w,
    int                        thumb_h)
{
    VideoThumbResult result;
    result.path = video_path;

    cv::VideoCapture cap(video_path);
    if (!cap.isOpened()) {
        result.error = "VideoCapture failed to open: " + video_path;
        return result;
    }

    result.frames.reserve(timestamps_sec.size());
    for (double ts : timestamps_sec) {
        cap.set(cv::CAP_PROP_POS_MSEC, ts * 1000.0);
        cv::Mat frame;
        if (!cap.read(frame)) {
            result.frames.emplace_back();  // empty Mat signals seek failure
            continue;
        }
        cv::Mat thumb;
        cv::resize(frame, thumb, cv::Size(thumb_w, thumb_h), 0.0, 0.0, cv::INTER_AREA);
        result.frames.push_back(std::move(thumb));
    }
    return result;
}

py::list extract_video_thumbnails_batch(
    const std::vector<std::string>& paths,
    const std::vector<double>&      timestamps_sec,
    int                             thumb_w,
    int                             thumb_h)
{
    const int N = static_cast<int>(paths.size());
    std::vector<VideoThumbResult> results(N);

    {
        py::gil_scoped_release release;

        #pragma omp parallel for schedule(dynamic)
        for (int i = 0; i < N; ++i)
            results[i] = extract_thumbnails(paths[i], timestamps_sec, thumb_w, thumb_h);
    }

    py::list out;
    for (const auto& r : results) {
        py::list frames;
        for (const auto& f : r.frames) {
            if (f.empty()) frames.append(py::none());
            else           frames.append(base::array_from_mat(f));
        }
        out.append(py::make_tuple(r.path, frames, r.error));
    }
    return out;
}

} // namespace base::video

// ---------------------------------------------------------------------------
// pybind11 registration (called from bindings.cpp)
// ---------------------------------------------------------------------------

void register_video(py::module_& m) {
    m.doc() = "Parallel video thumbnail extraction via OpenCV VideoCapture.";

    m.def("extract_video_thumbnails_batch",
          &base::video::extract_video_thumbnails_batch,
          py::arg("paths"),
          py::arg("timestamps_sec"),
          py::arg("thumb_w") = 256,
          py::arg("thumb_h") = 256,
          R"doc(
Extract thumbnails at given timestamps from a batch of video files.

Parameters
----------
paths : list[str]
    Paths to video files.
timestamps_sec : list[float]
    Timestamps (in seconds) at which to extract a frame from each video.
thumb_w, thumb_h : int
    Thumbnail dimensions.

Returns
-------
list of (path: str, frames: list[np.ndarray | None], error: str)
    Each element in frames corresponds to one timestamp.
    A frame is None if the seek or decode failed.
          )doc");
}
