// ---------------------------------------------------------------------------
// batch/src/images/image_batch.cpp
//
// Parallel image batch loading and thumbnail generation.
//
// C++ replacement for Rust `base::load_image_batch`.
// Implementation: Phase 2 of the Rust → C++ migration.
// See moon/archive/rust_to_cpp_migration.md §Phase 2
// ---------------------------------------------------------------------------

#include "image/image_batch.hpp"
#include "common.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <omp.h>

namespace py = pybind11;

namespace base::image {

py::list load_image_batch(
    const std::vector<std::string>& paths,
    int  thumb_w,
    int  thumb_h,
    bool keep_aspect)
{
    const int N = static_cast<int>(paths.size());
    std::vector<cv::Mat>       thumbs(N);
    std::vector<std::string>   errors(N);

    {
        py::gil_scoped_release release;

        #pragma omp parallel for schedule(dynamic)
        for (int i = 0; i < N; ++i) {
            cv::Mat img = cv::imread(paths[i], cv::IMREAD_COLOR);
            if (img.empty()) {
                errors[i] = "imread failed: " + paths[i];
                continue;
            }
            cv::Size target(thumb_w, thumb_h);
            if (keep_aspect) {
                double sx = static_cast<double>(thumb_w) / img.cols;
                double sy = static_cast<double>(thumb_h) / img.rows;
                double s  = std::min(sx, sy);
                target = cv::Size(
                    static_cast<int>(img.cols * s),
                    static_cast<int>(img.rows * s));
            }
            cv::resize(img, thumbs[i], target, 0.0, 0.0, cv::INTER_AREA);
        }
    }

    py::list result;
    for (int i = 0; i < N; ++i) {
        py::object arr = thumbs[i].empty()
            ? py::none().cast<py::object>()
            : py::object(base::array_from_mat(thumbs[i]));
        result.append(py::make_tuple(paths[i], arr, errors[i]));
    }
    return result;
}

} // namespace base::image

// ---------------------------------------------------------------------------
// pybind11 registration (called from bindings.cpp)
// ---------------------------------------------------------------------------

// Forward declaration — implemented in scan_files.cpp
namespace base::image::detail { void register_scan_files(py::module_& m); }

void register_image(py::module_& m) {
    m.doc() = "Parallel image batch loading, thumbnail generation, and filesystem scan.";

    m.def("load_image_batch",
          &base::image::load_image_batch,
          py::arg("paths"),
          py::arg("thumb_w")     = 256,
          py::arg("thumb_h")     = 256,
          py::arg("keep_aspect") = true,
          R"doc(
Load and thumbnail a batch of images in parallel.

Parameters
----------
paths : list[str]
    Absolute or relative paths to images.
thumb_w, thumb_h : int
    Target thumbnail dimensions in pixels.
keep_aspect : bool
    If True, fit the image inside (thumb_w × thumb_h) while preserving aspect ratio.

Returns
-------
list of (path: str, thumbnail: np.ndarray | None, error: str)
    thumbnail is a uint8 BGR array (H, W, 3); None on load failure.
    error is empty on success, descriptive on failure.
          )doc");

    base::image::detail::register_scan_files(m);
}
