// ---------------------------------------------------------------------------
// base/src/core/convert.cpp — image and video format conversion
// Phase 8 of Rust→C++ migration.
// ---------------------------------------------------------------------------
#include "base/core/convert.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <atomic>
#include <filesystem>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#ifdef _OPENMP
#  include <omp.h>
#endif

namespace py  = pybind11;
namespace fs  = std::filesystem;

namespace base::core {

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static cv::Mat crop_center(const cv::Mat& img, float target_ratio) {
    int w = img.cols, h = img.rows;
    int new_w, new_h;
    if (static_cast<float>(w) / h > target_ratio) {
        new_h = h;
        new_w = static_cast<int>(h * target_ratio);
    } else {
        new_w = w;
        new_h = static_cast<int>(w / target_ratio);
    }
    int x = (w - new_w) / 2, y = (h - new_h) / 2;
    return img(cv::Rect(x, y, new_w, new_h)).clone();
}

static cv::Mat pad_image(const cv::Mat& img, float target_ratio) {
    int w = img.cols, h = img.rows;
    int new_w, new_h;
    if (static_cast<float>(w) / h > target_ratio) {
        new_w = w;
        new_h = static_cast<int>(w / target_ratio);
    } else {
        new_h = h;
        new_w = static_cast<int>(h * target_ratio);
    }
    cv::Mat canvas(new_h, new_w, img.type(), cv::Scalar(0, 0, 0, 0));
    int x = (new_w - w) / 2, y = (new_h - h) / 2;
    img.copyTo(canvas(cv::Rect(x, y, w, h)));
    return canvas;
}

static cv::Mat stretch_image(const cv::Mat& img, float target_ratio) {
    int w = img.cols, h = img.rows;
    int new_w, new_h;
    if (static_cast<float>(w) / h > target_ratio) {
        new_w = w;
        new_h = static_cast<int>(w / target_ratio);
    } else {
        new_h = h;
        new_w = static_cast<int>(h * target_ratio);
    }
    cv::Mat result;
    cv::resize(img, result, cv::Size(new_w, new_h), 0, 0, cv::INTER_LANCZOS4);
    return result;
}

static cv::Mat apply_ar(const cv::Mat& img, std::optional<float> aspect_ratio,
                        const std::string& mode) {
    if (!aspect_ratio) return img;
    float r = *aspect_ratio;
    if (mode == "pad")     return pad_image(img, r);
    if (mode == "stretch") return stretch_image(img, r);
    return crop_center(img, r); // default: crop
}

static std::string extension_for_format(const std::string& fmt) {
    std::string f = fmt;
    std::transform(f.begin(), f.end(), f.begin(), ::tolower);
    if (f == "jpg" || f == "jpeg") return ".jpg";
    if (f == "png")  return ".png";
    if (f == "webp") return ".webp";
    if (f == "bmp")  return ".bmp";
    if (f == "tiff" || f == "tif") return ".tiff";
    if (f == "ico")  return ".ico";
    return "." + f;
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

bool convert_single_image(
    const std::string& input_path,
    const std::string& output_path,
    const std::string& output_format,
    bool delete_original,
    std::optional<float> aspect_ratio,
    const std::string& ar_mode)
{
    cv::Mat img = cv::imread(input_path, cv::IMREAD_UNCHANGED);
    if (img.empty()) return false;

    cv::Mat proc = apply_ar(img, aspect_ratio, ar_mode);

    // Ensure output_path has the right extension
    std::string out = output_path;
    if (!output_format.empty()) {
        std::string desired_ext = extension_for_format(output_format);
        if (fs::path(out).extension().string() != desired_ext)
            out = fs::path(out).replace_extension(desired_ext).string();
    }

    if (!cv::imwrite(out, proc)) return false;

    if (delete_original && input_path != out) {
        std::error_code ec;
        fs::remove(input_path, ec);
    }
    return true;
}

std::vector<std::string> convert_image_batch(
    const std::vector<std::pair<std::string, std::string>>& image_pairs,
    const std::string& output_format,
    bool delete_original,
    std::optional<float> aspect_ratio,
    const std::string& ar_mode)
{
    int N = static_cast<int>(image_pairs.size());
    std::vector<std::string> successes;
    std::vector<int> ok(N, 0);

#pragma omp parallel for schedule(dynamic)
    for (int i = 0; i < N; ++i) {
        bool res = convert_single_image(
            image_pairs[i].first, image_pairs[i].second,
            output_format, delete_original, aspect_ratio, ar_mode);
        ok[i] = res ? 1 : 0;
    }

    for (int i = 0; i < N; ++i)
        if (ok[i]) successes.push_back(image_pairs[i].second);
    return successes;
}

bool convert_video(
    const std::string& input_path,
    const std::string& output_path,
    bool delete_original)
{
    std::string cmd = "ffmpeg -y -i " + input_path + " " + output_path +
                      " > /dev/null 2>&1";
    int rc = std::system(cmd.c_str());
    if (rc == 0 && delete_original) {
        std::error_code ec;
        fs::remove(input_path, ec);
    }
    return rc == 0;
}

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

void register_convert(py::module_& m) {
    m.def("convert_single_image",
        [](const std::string& in, const std::string& out,
           const std::string& fmt, bool del,
           std::optional<float> ar, std::optional<std::string> mode) {
            py::gil_scoped_release rel;
            return base::core::convert_single_image(
                in, out, fmt, del, ar, mode.value_or("crop"));
        },
        py::arg("input_path"), py::arg("output_path"),
        py::arg("output_format"), py::arg("delete_original"),
        py::arg("aspect_ratio") = py::none(),
        py::arg("ar_mode") = py::none(),
        "Convert a single image to a new format with optional aspect-ratio transform.");

    m.def("convert_image_batch",
        [](const std::vector<std::pair<std::string,std::string>>& pairs,
           const std::string& fmt, bool del,
           std::optional<float> ar, std::optional<std::string> mode) {
            py::gil_scoped_release rel;
            return base::core::convert_image_batch(
                pairs, fmt, del, ar, mode.value_or("crop"));
        },
        py::arg("image_pairs"), py::arg("output_format"),
        py::arg("delete_original"),
        py::arg("aspect_ratio") = py::none(),
        py::arg("ar_mode") = py::none(),
        "Batch-convert images in parallel (OpenMP). Returns list of output paths that succeeded.");

    m.def("convert_video",
        [](const std::string& inp, const std::string& out, bool del) {
            py::gil_scoped_release rel;
            return base::core::convert_video(inp, out, del);
        },
        py::arg("input_path"), py::arg("output_path"),
        py::arg("delete_original"),
        "Transcode a video via ffmpeg subprocess. Returns True on success.");
}

} // namespace base::core
