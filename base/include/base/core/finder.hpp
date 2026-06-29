#pragma once
// ---------------------------------------------------------------------------
// base/include/base/core/finder.hpp
// Duplicate and perceptual-hash image finder — Phase 8.
// ---------------------------------------------------------------------------
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>
#include <pybind11/pybind11.h>

namespace base::core {

// SHA-256 grouping; returns only groups with ≥2 paths
std::unordered_map<std::string, std::vector<std::string>>
find_duplicate_images(
    const std::string& directory,
    const std::vector<std::string>& extensions,
    bool recursive);

// pHash grouping; Hamming ≤ threshold; returns only groups with ≥2 paths
std::unordered_map<std::string, std::vector<std::string>>
find_similar_images_phash(
    const std::string& directory,
    const std::vector<std::string>& extensions,
    uint32_t threshold);

void register_finder(pybind11::module_& m);

} // namespace base::core
