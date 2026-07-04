// ---------------------------------------------------------------------------
// batch/src/images/image_batch.cpp
//
// Parallel image batch loading and thumbnail generation.
//
// C++ replacement for Rust `base::load_image_batch`.
// Implementation: Phase 2 of the Rust → C++ migration.
// See moon/archive/rust_to_cpp_migration.md §Phase 2
//
// Performance upgrades (thumbnail loading optimization):
//   - Reduced-resolution JPEG decode (IMREAD_REDUCED_COLOR_*) — the libjpeg
//     IDCT-scaling path decodes 4K sources up to ~8x faster for thumbnails.
//   - Optional RGB output so the Python side can build a QImage directly
//     without a per-image numpy channel-reversal copy.
//   - Optional persistent disk thumbnail cache (JPEG, mtime-invalidated) so
//     revisiting a directory or gallery page skips full-size decoding.
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

#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace py = pybind11;
namespace fs = std::filesystem;

namespace base::image {

namespace {

/// FNV-1a 64-bit hash — stable cache key for a source path.
uint64_t fnv1a_64(const std::string& s)
{
    uint64_t h = 14695981039346656037ULL;
    for (unsigned char c : s) {
        h ^= c;
        h *= 1099511628211ULL;
    }
    return h;
}

/// Cache file for (source path, thumbnail size): <fnv64hex>_<size>.jpg
fs::path cache_path_for(const fs::path& cache_dir, const std::string& src, int size)
{
    char name[64];
    std::snprintf(name, sizeof(name), "%016llx_%d.jpg",
                  static_cast<unsigned long long>(fnv1a_64(src)), size);
    return cache_dir / name;
}

/// Read a whole file into memory. Returns empty vector on failure.
std::vector<uchar> read_file_bytes(const std::string& path)
{
    std::ifstream in(path, std::ios::binary | std::ios::ate);
    if (!in)
        return {};
    const std::streamsize n = in.tellg();
    if (n <= 0)
        return {};
    std::vector<uchar> buf(static_cast<size_t>(n));
    in.seekg(0);
    in.read(reinterpret_cast<char*>(buf.data()), n);
    if (!in)
        return {};
    return buf;
}

/// Decode `buf` so that min(width, height) >= min_dim if possible.
/// For JPEG sources, walk the IDCT-scaling ladder (1/8 -> 1/4 -> 1/2 -> full)
/// and stop at the first reduction that still satisfies min_dim — decoding a
/// 4000px photo at 1/8 scale is far cheaper than a full decode when the
/// requested thumbnail is only ~256px. Non-JPEG codecs ignore the reduced
/// flags, so decode those once at full resolution.
cv::Mat decode_min_dim(const std::vector<uchar>& buf, int min_dim)
{
    const bool is_jpeg = buf.size() >= 2 && buf[0] == 0xFF && buf[1] == 0xD8;
    if (!is_jpeg)
        return cv::imdecode(buf, cv::IMREAD_COLOR);

    static const int ladder[] = {
        cv::IMREAD_REDUCED_COLOR_8,
        cv::IMREAD_REDUCED_COLOR_4,
        cv::IMREAD_REDUCED_COLOR_2,
        cv::IMREAD_COLOR,
    };
    for (int flag : ladder) {
        cv::Mat img = cv::imdecode(buf, flag);
        if (img.empty())
            continue;
        if (flag == cv::IMREAD_COLOR || std::min(img.cols, img.rows) >= min_dim)
            return img;
    }
    return cv::Mat();
}

} // namespace

py::list load_image_batch(
    const std::vector<std::string>& paths,
    int  thumb_w,
    int  thumb_h,
    bool keep_aspect,
    bool rgb,
    const std::string& cache_dir)
{
    const int N = static_cast<int>(paths.size());
    std::vector<cv::Mat>       thumbs(N);
    std::vector<std::string>   errors(N);

    const bool use_cache = !cache_dir.empty();
    fs::path cache_root(cache_dir);
    if (use_cache) {
        std::error_code ec;
        fs::create_directories(cache_root, ec);   // best-effort; cache is optional
    }
    const int min_dim = std::max(thumb_w, thumb_h);

    {
        py::gil_scoped_release release;

        #pragma omp parallel for schedule(dynamic)
        for (int i = 0; i < N; ++i) {
            std::error_code ec;

            // 1. Disk cache hit: reload the small JPEG instead of the source.
            fs::path cpath;
            if (use_cache) {
                cpath = cache_path_for(cache_root, paths[i], min_dim);
                if (fs::exists(cpath, ec)) {
                    const auto src_time   = fs::last_write_time(paths[i], ec);
                    const auto cache_time = fs::last_write_time(cpath, ec);
                    if (!ec && cache_time >= src_time) {
                        cv::Mat cached = cv::imread(cpath.string(), cv::IMREAD_COLOR);
                        if (!cached.empty()) {
                            thumbs[i] = cached;
                            continue;
                        }
                    }
                }
            }

            // 2. Decode at reduced resolution when the codec allows it.
            std::vector<uchar> buf = read_file_bytes(paths[i]);
            cv::Mat img = buf.empty() ? cv::Mat() : decode_min_dim(buf, min_dim);
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
                    std::max(1, static_cast<int>(img.cols * s)),
                    std::max(1, static_cast<int>(img.rows * s)));
            }
            if (target == img.size())
                thumbs[i] = img;
            else
                cv::resize(img, thumbs[i], target, 0.0, 0.0, cv::INTER_AREA);

            // 3. Persist thumbnail for future calls (BGR JPEG).
            if (use_cache) {
                static const std::vector<int> jpeg_params = {
                    cv::IMWRITE_JPEG_QUALITY, 90};
                cv::imwrite(cpath.string(), thumbs[i], jpeg_params);
            }
        }

        // Convert to RGB after the cache write so cached files stay BGR JPEG.
        if (rgb) {
            #pragma omp parallel for schedule(static)
            for (int i = 0; i < N; ++i) {
                if (!thumbs[i].empty())
                    cv::cvtColor(thumbs[i], thumbs[i], cv::COLOR_BGR2RGB);
            }
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
          py::arg("rgb")         = false,
          py::arg("cache_dir")   = "",
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
rgb : bool
    If True, return RGB arrays (ready for QImage) instead of BGR.
cache_dir : str
    If non-empty, persist thumbnails as JPEGs in this directory and reuse
    them on later calls (invalidated when the source file is newer).

Returns
-------
list of (path: str, thumbnail: np.ndarray | None, error: str)
    thumbnail is a uint8 array (H, W, 3), BGR by default or RGB when rgb=True;
    None on load failure.
    error is empty on success, descriptive on failure.
          )doc");

    base::image::detail::register_scan_files(m);
}
