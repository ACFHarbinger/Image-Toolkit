// ---------------------------------------------------------------------------
// base/src/core/merger.cpp — image canvas merging
// Phase 8 of Rust→C++ migration.
// Two-pass streaming: Pass 1 reads headers (imread IMREAD_UNCHANGED, drop
// immediately) to compute canvas dims; Pass 2 loads, blits, and drops.
// ---------------------------------------------------------------------------
#include "core/merger.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cmath>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

namespace py = pybind11;

namespace base::core {

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// White canvas, 3-channel BGR (alpha-aware sources get flattened on blit).
static cv::Mat make_white_canvas(int w, int h) {
    return cv::Mat(h, w, CV_8UC3, cv::Scalar(255, 255, 255));
}

// Flatten alpha channel if present before blitting.
static cv::Mat to_bgr(cv::Mat img) {
    if (img.channels() == 4)
        cv::cvtColor(img, img, cv::COLOR_BGRA2BGR);
    else if (img.channels() == 1)
        cv::cvtColor(img, img, cv::COLOR_GRAY2BGR);
    return img;
}

// Blit src onto dst at (x, y), clipping to dst boundaries.
static void blit(cv::Mat& dst, const cv::Mat& src, int x, int y) {
    cv::Rect roi(x, y,
                 std::min(src.cols, dst.cols - x),
                 std::min(src.rows, dst.rows - y));
    if (roi.width <= 0 || roi.height <= 0) return;
    src(cv::Rect(0, 0, roi.width, roi.height)).copyTo(dst(roi));
}

// ---------------------------------------------------------------------------
// merge_images_horizontal
// ---------------------------------------------------------------------------

bool merge_images_horizontal(
    const std::vector<std::string>& image_paths,
    const std::string& output_path,
    uint32_t spacing,
    const std::string& align_mode)
{
    if (image_paths.empty()) return false;

    // Pass 1 — collect dimensions
    std::vector<cv::Size> dims;
    for (const auto& p : image_paths) {
        cv::Mat img = cv::imread(p, cv::IMREAD_UNCHANGED);
        if (img.empty()) continue;
        dims.push_back(img.size());
    } // img dropped here each iteration
    if (dims.empty()) return false;

    int max_h = 0;
    for (const auto& d : dims) max_h = std::max(max_h, d.height);

    int total_w = static_cast<int>((dims.size() - 1) * spacing);
    for (const auto& d : dims) total_w += d.width;

    // Pass 2 — blit
    cv::Mat canvas = make_white_canvas(total_w, max_h);
    int cur_x = 0;
    int di    = 0;
    for (const auto& p : image_paths) {
        cv::Mat img = cv::imread(p, cv::IMREAD_UNCHANGED);
        if (img.empty()) { ++di; continue; }
        int w = img.cols, h = img.rows;

        if (align_mode == "stretch" || align_mode == "squish")
            cv::resize(img, img, cv::Size(w, max_h));

        img = to_bgr(img);
        int y_off = 0;
        if (align_mode == "bottom")  y_off = max_h - img.rows;
        else if (align_mode == "center") y_off = (max_h - img.rows) / 2;

        blit(canvas, img, cur_x, y_off);
        cur_x += img.cols + static_cast<int>(spacing);
        ++di;
        // img dropped here
    }

    return cv::imwrite(output_path, canvas);
}

// ---------------------------------------------------------------------------
// merge_images_vertical
// ---------------------------------------------------------------------------

bool merge_images_vertical(
    const std::vector<std::string>& image_paths,
    const std::string& output_path,
    uint32_t spacing,
    const std::string& align_mode)
{
    if (image_paths.empty()) return false;

    std::vector<cv::Size> dims;
    for (const auto& p : image_paths) {
        cv::Mat img = cv::imread(p, cv::IMREAD_UNCHANGED);
        if (img.empty()) continue;
        dims.push_back(img.size());
    }
    if (dims.empty()) return false;

    int max_w = 0;
    for (const auto& d : dims) max_w = std::max(max_w, d.width);

    int total_h = static_cast<int>((dims.size() - 1) * spacing);
    for (const auto& d : dims) total_h += d.height;

    cv::Mat canvas = make_white_canvas(max_w, total_h);
    int cur_y = 0;
    for (const auto& p : image_paths) {
        cv::Mat img = cv::imread(p, cv::IMREAD_UNCHANGED);
        if (img.empty()) continue;
        img = to_bgr(img);

        int x_off = 0;
        if (align_mode == "right")  x_off = max_w - img.cols;
        else if (align_mode == "center") x_off = (max_w - img.cols) / 2;

        blit(canvas, img, x_off, cur_y);
        cur_y += img.rows + static_cast<int>(spacing);
    }

    return cv::imwrite(output_path, canvas);
}

// ---------------------------------------------------------------------------
// merge_images_grid
// ---------------------------------------------------------------------------

bool merge_images_grid(
    const std::vector<std::string>& image_paths,
    const std::string& output_path,
    uint32_t rows,
    uint32_t cols,
    uint32_t spacing)
{
    if (image_paths.empty()) return false;

    std::vector<cv::Size> dims;
    for (const auto& p : image_paths) {
        cv::Mat img = cv::imread(p, cv::IMREAD_UNCHANGED);
        if (img.empty()) continue;
        dims.push_back(img.size());
    }
    if (dims.empty()) return false;

    int max_w = 0, max_h = 0;
    for (const auto& d : dims) {
        max_w = std::max(max_w, d.width);
        max_h = std::max(max_h, d.height);
    }

    int total_w = static_cast<int>(cols * max_w + (cols - 1) * spacing);
    int total_h = static_cast<int>(rows * max_h + (rows - 1) * spacing);

    cv::Mat canvas = make_white_canvas(total_w, total_h);
    int idx = 0;
    for (const auto& p : image_paths) {
        uint32_t row = static_cast<uint32_t>(idx) / cols;
        uint32_t col = static_cast<uint32_t>(idx) % cols;
        if (row >= rows) break;

        cv::Mat img = cv::imread(p, cv::IMREAD_UNCHANGED);
        if (img.empty()) { ++idx; continue; }
        img = to_bgr(img);

        int x = static_cast<int>(col * (max_w + spacing)) + (max_w - img.cols) / 2;
        int y = static_cast<int>(row * (max_h + spacing)) + (max_h - img.rows) / 2;
        blit(canvas, img, x, y);
        ++idx;
    }

    return cv::imwrite(output_path, canvas);
}

// ---------------------------------------------------------------------------
// pybind11 registration
// ---------------------------------------------------------------------------

void register_merger(py::module_& m) {
    m.def("merge_images_horizontal",
        [](const std::vector<std::string>& paths, const std::string& out,
           uint32_t spacing, const std::string& align) {
            py::gil_scoped_release rel;
            return base::core::merge_images_horizontal(paths, out, spacing, align);
        },
        py::arg("image_paths"), py::arg("output_path"),
        py::arg("spacing") = 0, py::arg("align_mode") = "center",
        "Merge images side-by-side. align_mode: top|bottom|center|stretch.");

    m.def("merge_images_vertical",
        [](const std::vector<std::string>& paths, const std::string& out,
           uint32_t spacing, const std::string& align) {
            py::gil_scoped_release rel;
            return base::core::merge_images_vertical(paths, out, spacing, align);
        },
        py::arg("image_paths"), py::arg("output_path"),
        py::arg("spacing") = 0, py::arg("align_mode") = "center",
        "Merge images top-to-bottom. align_mode: left|right|center.");

    m.def("merge_images_grid",
        [](const std::vector<std::string>& paths, const std::string& out,
           std::optional<uint32_t> rows, std::optional<uint32_t> cols, uint32_t spacing) {
            uint32_t r = rows ? *rows : 0;
            uint32_t c = cols ? *cols : 0;
            if (paths.empty()) return false;
            if (r == 0 && c == 0) {
                c = static_cast<uint32_t>(std::ceil(std::sqrt(paths.size())));
                r = static_cast<uint32_t>((paths.size() + c - 1) / c);
            } else if (r == 0) {
                r = static_cast<uint32_t>((paths.size() + c - 1) / c);
            } else if (c == 0) {
                c = static_cast<uint32_t>((paths.size() + r - 1) / r);
            }
            py::gil_scoped_release rel;
            return base::core::merge_images_grid(paths, out, r, c, spacing);
        },
        py::arg("image_paths"), py::arg("output_path"),
        py::arg("rows") = std::nullopt, py::arg("cols") = std::nullopt, py::arg("spacing") = 0,
        "Arrange images in a grid; cells are max(w)×max(h), images centered.");
}

} // namespace base::core
