#pragma once

// ---------------------------------------------------------------------------
// batch/common.hpp
//
// Zero-copy numpy <-> cv::Mat converters and shared error/assertion macros.
// IMPORTANT lifetime rules (enforced by code review):
//   - mat_from_array / mat_from_f32 share Python memory — the cv::Mat MUST
//     NOT outlive the Python array object (i.e. stay on the stack within the
//     pybind11 function body, never store as a class member or return it).
//   - array_from_mat / array_from_f32 perform a deep copy and are safe to
//     return to Python.
// ---------------------------------------------------------------------------

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <opencv2/core.hpp>

#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace py = pybind11;

namespace base {

// ---------------------------------------------------------------------------
// Input converters (zero-copy, share Python-owned memory)
// ---------------------------------------------------------------------------

/// Convert a C-contiguous uint8 numpy array of shape (H, W) or (H, W, C)
/// to a cv::Mat that shares the same memory.
inline cv::Mat mat_from_array(
    py::array_t<uint8_t, py::array::c_style | py::array::forcecast> arr)
{
    py::buffer_info buf = arr.request();
    if (buf.ndim < 2 || buf.ndim > 3)
        throw std::invalid_argument(
            "mat_from_array: expected 2-D (H,W) or 3-D (H,W,C) uint8 array, "
            "got ndim=" + std::to_string(buf.ndim));

    int rows     = static_cast<int>(buf.shape[0]);
    int cols     = static_cast<int>(buf.shape[1]);
    int channels = (buf.ndim == 3) ? static_cast<int>(buf.shape[2]) : 1;

    int cv_type;
    switch (channels) {
        case 1:  cv_type = CV_8UC1; break;
        case 3:  cv_type = CV_8UC3; break;
        case 4:  cv_type = CV_8UC4; break;
        default:
            throw std::invalid_argument(
                "mat_from_array: unsupported channel count " +
                std::to_string(channels));
    }
    // step = row stride in bytes
    std::size_t step = static_cast<std::size_t>(buf.strides[0]);
    return cv::Mat(rows, cols, cv_type, buf.ptr, step);
}

/// Convert a C-contiguous float32 numpy array of shape (H, W) or (H, W, C)
/// to a CV_32F cv::Mat that shares the same memory.
inline cv::Mat mat_from_f32(
    py::array_t<float, py::array::c_style | py::array::forcecast> arr)
{
    py::buffer_info buf = arr.request();
    if (buf.ndim < 2 || buf.ndim > 3)
        throw std::invalid_argument(
            "mat_from_f32: expected 2-D or 3-D float32 array");

    int rows     = static_cast<int>(buf.shape[0]);
    int cols     = static_cast<int>(buf.shape[1]);
    int channels = (buf.ndim == 3) ? static_cast<int>(buf.shape[2]) : 1;

    int cv_type;
    switch (channels) {
        case 1:  cv_type = CV_32FC1; break;
        case 3:  cv_type = CV_32FC3; break;
        case 4:  cv_type = CV_32FC4; break;
        default:
            throw std::invalid_argument(
                "mat_from_f32: unsupported channel count " +
                std::to_string(channels));
    }
    std::size_t step = static_cast<std::size_t>(buf.strides[0]);
    return cv::Mat(rows, cols, cv_type, buf.ptr, step);
}

// ---------------------------------------------------------------------------
// Output converters (deep copy — safe to return to Python)
// ---------------------------------------------------------------------------

/// Deep-copy a CV_8U cv::Mat into an owned numpy array.
/// Shape is (H, W) for single-channel or (H, W, C) for multi-channel.
inline py::array_t<uint8_t> array_from_mat(const cv::Mat& mat)
{
    if (mat.depth() != CV_8U)
        throw std::invalid_argument("array_from_mat: expected CV_8U mat");

    std::vector<ssize_t> shape, strides;
    if (mat.channels() == 1) {
        shape   = {mat.rows, mat.cols};
        strides = {static_cast<ssize_t>(mat.step[0]),
                   static_cast<ssize_t>(mat.step[1])};
    } else {
        shape   = {mat.rows, mat.cols, mat.channels()};
        strides = {static_cast<ssize_t>(mat.step[0]),
                   static_cast<ssize_t>(mat.step[1]),
                   static_cast<ssize_t>(mat.elemSize1())};
    }
    auto result = py::array_t<uint8_t>(shape);
    // cv::Mat::copyTo guarantees a contiguous output
    cv::Mat dst(mat.rows, mat.cols, mat.type(), result.mutable_data());
    mat.copyTo(dst);
    return result;
}

/// Deep-copy a CV_32F cv::Mat into an owned float32 numpy array.
inline py::array_t<float> array_from_f32(const cv::Mat& mat)
{
    if (mat.depth() != CV_32F)
        throw std::invalid_argument("array_from_f32: expected CV_32F mat");

    std::vector<ssize_t> shape, strides;
    if (mat.channels() == 1) {
        shape   = {mat.rows, mat.cols};
        strides = {static_cast<ssize_t>(mat.step[0]),
                   static_cast<ssize_t>(mat.step[1])};
    } else {
        shape   = {mat.rows, mat.cols, mat.channels()};
        strides = {static_cast<ssize_t>(mat.step[0]),
                   static_cast<ssize_t>(mat.step[1]),
                   static_cast<ssize_t>(mat.elemSize1())};
    }
    auto result = py::array_t<float>(shape);
    cv::Mat dst(mat.rows, mat.cols, mat.type(), result.mutable_data());
    mat.copyTo(dst);
    return result;
}

// ---------------------------------------------------------------------------
// Seam path converters
// ---------------------------------------------------------------------------

/// Owned copy: std::vector<int> → numpy int32 array.
inline py::array_t<int32_t> path_to_array(const std::vector<int>& path)
{
    auto out = py::array_t<int32_t>(static_cast<ssize_t>(path.size()));
    std::copy(path.begin(), path.end(), out.mutable_data());
    return out;
}

/// View: numpy int32 array → std::vector<int> (copies data).
inline std::vector<int> path_from_array(py::array_t<int32_t> arr)
{
    py::buffer_info buf = arr.request();
    const int32_t* ptr = static_cast<const int32_t*>(buf.ptr);
    return std::vector<int>(ptr, ptr + buf.size);
}

// ---------------------------------------------------------------------------
// Error / assertion helpers
// ---------------------------------------------------------------------------

#define BATCH_CHECK(cond, msg)                                      \
    do {                                                            \
        if (!(cond))                                                \
            throw std::invalid_argument(                            \
                std::string("[batch] assertion failed: ") + (msg)); \
    } while (false)

#define BATCH_NOT_IMPLEMENTED(fn)                                       \
    throw std::runtime_error(                                           \
        std::string("[batch] ") + (fn) + " is not yet implemented. "   \
        "See moon/roadmaps/asp_cpp_migration.md for the implementation roadmap.")

} // namespace batch
