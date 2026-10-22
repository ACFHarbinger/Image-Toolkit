// Bounded gallery stills for the Tauri asset scope (S-01, #887).
//
// Writes a JPEG whose long edge is at most max_edge into cache_dir and
// returns that path. Pixel buffers stay in this function. Video and GIF
// use the middle reported frame. Animated playback is not this call.

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

#include "common.hpp"

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

#ifndef _WIN32
#include <unistd.h>
#endif

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

// imwrite follows an existing symlink and would overwrite whatever it
// points at before a later canonical-path check could reject it. Encode
// first, create a new file with an exclusive open, then publish that name.
// POSIX rename replaces a symlink and does not follow it. On Windows the
// publish uses MoveFileEx only after DeleteFile has removed a symlink,
// which deletes the link and not its target.
bool write_exclusive(const fs::path& path, const std::vector<uchar>& encoded)
{
#ifdef _WIN32
    const HANDLE handle = CreateFileW(
        path.c_str(),
        GENERIC_WRITE,
        0,
        nullptr,
        CREATE_NEW,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (handle == INVALID_HANDLE_VALUE) {
        return false;
    }
    std::size_t offset = 0;
    while (offset < encoded.size()) {
        DWORD wrote = 0;
        const auto chunk = static_cast<DWORD>(
            (std::min)(encoded.size() - offset, static_cast<std::size_t>(1u << 20)));
        if (!WriteFile(handle, encoded.data() + offset, chunk, &wrote, nullptr) || wrote == 0) {
            CloseHandle(handle);
            DeleteFileW(path.c_str());
            return false;
        }
        offset += wrote;
    }
    const BOOL flushed = FlushFileBuffers(handle);
    CloseHandle(handle);
    if (!flushed) {
        DeleteFileW(path.c_str());
        return false;
    }
    return true;
#else
    FILE* file = std::fopen(path.c_str(), "wbx");
    if (file == nullptr) {
        return false;
    }
    const std::size_t wrote = std::fwrite(encoded.data(), 1, encoded.size(), file);
    const int flushed = std::fflush(file);
    const int synced = ::fsync(::fileno(file));
    const int closed = std::fclose(file);
    if (wrote != encoded.size() || flushed != 0 || synced != 0 || closed != 0) {
        fs::remove(path);
        return false;
    }
    return true;
#endif
}

bool publish_cache_file(const fs::path& temp, const fs::path& dest)
{
#ifdef _WIN32
    for (int attempt = 0; attempt < 3; ++attempt) {
        std::error_code status_error;
        const fs::file_status status = fs::symlink_status(dest, status_error);
        if (!status_error && fs::is_symlink(status)) {
            if (!DeleteFileW(dest.c_str())) {
                return false;
            }
            continue;
        }
        if (MoveFileExW(
                temp.c_str(),
                dest.c_str(),
                MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
            return true;
        }
        return false;
    }
    return false;
#else
    std::error_code rename_error;
    fs::rename(temp, dest, rename_error);
    return !rename_error;
#endif
}

bool commit_jpeg(const fs::path& root, const fs::path& dest, const cv::Mat& image, std::string& error)
{
    std::vector<uchar> encoded;
    const std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, 85};
    if (!cv::imencode(".jpg", image, encoded, params) || encoded.empty()) {
        error = "imwrite failed";
        return false;
    }

    fs::path temp;
    bool written = false;
    for (int attempt = 0; attempt < 8 && !written; ++attempt) {
        const auto ticks = static_cast<unsigned long long>(
            std::chrono::steady_clock::now().time_since_epoch().count());
        char name[192];
        std::snprintf(
            name,
            sizeof(name),
            "%s.%d.%llx.tmp",
            dest.filename().string().c_str(),
            attempt,
            ticks);
        temp = root / name;
        if (!confined(root, temp)) {
            error = "cache path escaped the render directory";
            return false;
        }
        written = write_exclusive(temp, encoded);
    }
    if (!written) {
        error = "imwrite failed";
        return false;
    }

    if (!publish_cache_file(temp, dest)) {
        fs::remove(temp);
        error = "imwrite failed";
        return false;
    }
    std::error_code status_error;
    const fs::file_status status = fs::symlink_status(dest, status_error);
    const fs::path canonical = fs::weakly_canonical(dest);
    if (status_error || !fs::is_regular_file(status) || !confined(root, canonical)) {
        if (!status_error && fs::is_symlink(status)) {
            fs::remove(dest);
        }
        error = "written still escaped the render directory";
        return false;
    }
    return true;
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
            if (!commit_jpeg(root, dest, fitted, row.error)) {
                row.frame_index = -1;
                continue;
            }
            row.cache_path = fs::weakly_canonical(dest).string();
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
