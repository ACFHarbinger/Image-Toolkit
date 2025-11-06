#pragma once

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <filesystem>
#include <algorithm>
#include <stdexcept>
#include <tuple>

// --- CImg Configuration ---
// These defines must be set *before* including CImg.h

// 1. Disable the CImg display (GUI) functionality, which is not needed
//    and avoids a dependency on the X11 library.
#define cimg_display 0

// 2. Enable support for JPEG and PNG formats.
//    (Requires linking libjpeg and libpng)
#define cimg_use_jpeg
#define cimg_use_png

// 3. Include the CImg header file (must be in your include path)
#include "CImg.h"

// --- C++ Namespace Setup ---

namespace fs = std::filesystem;
using namespace cimg_library;

/**
 * @brief Global definitions and utilities for the Image Toolkit.
 */
namespace ImageToolkit
{
    // C++ equivalent of SUPPORTED_IMG_FORMATS
    const std::vector<std::string> SUPPORTED_IMG_FORMATS = {
        "jpg", "jpeg", "png", "bmp", "gif"
    };

    /**
     * @brief Custom exception for file system or image errors.
     */
    class ImageToolException : public std::runtime_error {
    public:
        explicit ImageToolException(const std::string& message)
            : std::runtime_error("ImageTool Error: " + message) {}
    };

    /**
     * @brief Helper to convert a string to lowercase.
     */
    inline std::string to_lower(const std::string& str) {
        std::string data = str;
        std::transform(data.begin(), data.end(), data.begin(),
            [](unsigned char c){ return std::tolower(c); });
        return data;
    }

} // namespace ImageToolkit