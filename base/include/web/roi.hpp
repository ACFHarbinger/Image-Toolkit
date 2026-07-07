// ---------------------------------------------------------------------------
// base/include/web/roi.hpp — Region-of-Interest cropping + saliency auto-crop
// for the reverse-image-search preprocessing pipeline.
//
// Adapted from the tmp/ Rust-adjacent C++ starter (imagetoolkit::core) into the
// project's base:: namespace + pybind11 submodule convention.
// ---------------------------------------------------------------------------
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include <pybind11/pybind11.h>

namespace base::roi {

// Pixel-space region in the coordinate system of the source image on disk.
struct RoiRect {
    int x = 0;
    int y = 0;
    int width = 0;
    int height = 0;
    bool is_valid() const { return width > 0 && height > 0; }
};

struct RoiCropResult {
    bool ok = false;
    std::string error;
    std::vector<uint8_t> data;   // encoded JPEG buffer
    std::string temp_path;       // also persisted to a temp file
    int width = 0;
    int height = 0;
};

// Clamp `roi` to the bounds of an image of size (image_width, image_height).
RoiRect clamp_roi(const RoiRect& roi, int image_width, int image_height);

// Load `image_path`, crop to `roi` (auto-clamped), return the crop as an
// in-memory JPEG buffer and as a temp file. Never throws — failures land in
// RoiCropResult::ok/::error.
RoiCropResult crop_roi(const std::string& image_path, const RoiRect& roi,
                       int jpeg_quality = 95);

// Lightweight spectral-residual saliency auto-crop: propose a bounding box
// around the most salient subject. Returns an invalid rect if nothing stands
// out (caller falls back to the full image).
RoiRect auto_crop(const std::string& image_path, double coverage = 0.9);

void register_roi(pybind11::module_& m);

}  // namespace base::roi
