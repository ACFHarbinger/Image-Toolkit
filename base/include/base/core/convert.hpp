#pragma once
// ---------------------------------------------------------------------------
// base/include/base/core/convert.hpp
// Image and video format conversion — Phase 8.
// ---------------------------------------------------------------------------
#include <optional>
#include <string>
#include <utility>
#include <vector>
#include <pybind11/pybind11.h>

namespace base::core {

bool convert_single_image(
    const std::string& input_path,
    const std::string& output_path,
    const std::string& output_format,
    bool delete_original,
    std::optional<float> aspect_ratio = std::nullopt,
    const std::string& ar_mode = "crop");

std::vector<std::string> convert_image_batch(
    const std::vector<std::pair<std::string, std::string>>& image_pairs,
    const std::string& output_format,
    bool delete_original,
    std::optional<float> aspect_ratio = std::nullopt,
    const std::string& ar_mode = "crop");

bool convert_video(
    const std::string& input_path,
    const std::string& output_path,
    bool delete_original);

void register_convert(pybind11::module_& m);

} // namespace base::core
