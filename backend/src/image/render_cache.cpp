// Bounded gallery stills for the Tauri asset scope (S-01, #887).
//
// Writes a JPEG whose long edge is at most max_edge into cache_dir and
// returns that path. Pixel buffers stay in this function. Video and GIF
// use the middle reported frame. Animated playback is not this call.

#include "common.hpp"

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

namespace py = pybind11;
namespace fs = std::filesystem;

namespace base::image {
namespace {

uint64_t fnv1a_64(const std::string& text)
{
    uint64_t hash = 14695981039346656037ULL;
    for (unsigned char ch : text) {
        hash ^= ch;
        hash *= 1099511628211ULL;
    }
    return hash;
}

int clamp_edge(int edge)
{
    return std::clamp(edge, 16, 512);
}

bool is_motion(const fs::path& path)
{
    std::string ext = path.extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    static const char* extensions[] = {
        ".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".gif", ".mpg", ".mpeg",
    };
    return std::any_of(std::begin(extensions), std::end(extensions), [&](const char* candidate) {
        return ext == candidate;
    });
}

cv::Mat fit_long_edge(const cv::Mat& source, int edge)
{
    const int longest = std::max(source.cols, source.rows);
    if (longest <= edge) {
        return source;
    }
    const double scale = static_cast<double>(edge) / static_cast<double>(longest);
    cv::Mat fitted;
    cv::resize(
        source,
        fitted,
        cv::Size(
            std::max(1, static_cast<int>(source.cols * scale)),
            std::max(1, static_cast<int>(source.rows * scale))),
        0.0,
        0.0,
        cv::INTER_AREA);
    return fitted;
}

bool confined(const fs::path& root, const fs::path& dest)
{
    const fs::path relative = dest.lexically_relative(root);
    const std::string text = relative.generic_string();
    const bool escapes = text == ".." || text.rfind("../", 0) == 0;
    return !text.empty() && text != "." && !escapes;
}

cv::Mat middle_motion_frame(const std::string& path, int& frame_index, std::string& error)
{
    cv::VideoCapture capture(path);
    if (!capture.isOpened()) {
        error = "VideoCapture failed to open";
        return {};
    }
    const double reported = capture.get(cv::CAP_PROP_FRAME_COUNT);
    frame_index = 0;
    if (reported >= 2.0 && reported < 1.0e7) {
        frame_index = static_cast<int>(std::floor(reported / 2.0));
        capture.set(cv::CAP_PROP_POS_FRAMES, static_cast<double>(frame_index));
    }
    cv::Mat frame;
    if (!capture.read(frame) || frame.empty()) {
        capture.set(cv::CAP_PROP_POS_FRAMES, 0.0);
        frame_index = 0;
        if (!capture.read(frame) || frame.empty()) {
            error = "middle frame decode failed";
            return {};
        }
    }
    return frame;
}

} // namespace

py::list write_render_stills(
    const std::vector<std::string>& paths,
    const std::string& cache_dir,
    int max_edge)
{
    if (cache_dir.empty()) {
        throw std::invalid_argument("cache_dir is required");
    }
    const int edge = clamp_edge(max_edge);
    std::error_code mkdir_error;
    fs::create_directories(cache_dir, mkdir_error);
    if (mkdir_error) {
        throw std::invalid_argument("cache_dir cannot be created");
    }
    const fs::path root = fs::weakly_canonical(cache_dir);

    struct Row {
        std::string source;
        std::string cache_path;
        std::string error;
        std::string kind;
        int frame_index = -1;
    };
    std::vector<Row> rows(paths.size());

    {
        py::gil_scoped_release release;
        for (std::size_t index = 0; index < paths.size(); ++index) {
            Row& row = rows[index];
            row.source = paths[index];
            char name[80];
            std::snprintf(
                name,
                sizeof(name),
                "%016llx_%d.jpg",
                static_cast<unsigned long long>(fnv1a_64(paths[index])),
                edge);
            const fs::path dest = root / name;
            if (!confined(root, dest)) {
                row.error = "cache path escaped the render directory";
                continue;
            }

            cv::Mat decoded;
            if (is_motion(paths[index])) {
                row.kind = "video";
                decoded = middle_motion_frame(paths[index], row.frame_index, row.error);
            } else {
                row.kind = "image";
                decoded = cv::imread(paths[index], cv::IMREAD_COLOR);
                if (decoded.empty()) {
                    row.error = "imread failed";
                }
            }
            if (decoded.empty()) {
                continue;
            }
            const cv::Mat fitted = fit_long_edge(decoded, edge);
            const std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, 85};
            if (!cv::imwrite(dest.string(), fitted, params)) {
                row.error = "imwrite failed";
                row.frame_index = -1;
                continue;
            }
            const fs::path written = fs::weakly_canonical(dest);
            if (!confined(root, written)) {
                fs::remove(dest);
                row.error = "written still escaped the render directory";
                row.frame_index = -1;
                continue;
            }
            row.cache_path = written.string();
        }
    }

    py::list result;
    for (const Row& row : rows) {
        result.append(py::make_tuple(
            row.source, row.cache_path, row.error, row.kind, row.frame_index));
    }
    return result;
}

} // namespace base::image

void register_render_cache(py::module_& module)
{
    module.def(
        "write_render_stills",
        &base::image::write_render_stills,
        py::arg("paths"),
        py::arg("cache_dir"),
        py::arg("max_edge") = 256,
        R"doc(
Write bounded gallery stills into cache_dir.

Video and GIF sources use the middle frame reported by the container.
The return value is paths and errors, never pixel buffers. max_edge is
clamped to 16..512.
        )doc");
}
