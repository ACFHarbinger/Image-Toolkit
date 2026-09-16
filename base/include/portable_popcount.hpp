#pragma once
// ---------------------------------------------------------------------------
// base/include/portable_popcount.hpp
//
// __builtin_popcountll is a GCC/Clang extension; MSVC has no equivalent
// spelling (C++20's std::popcount would work everywhere, but this project
// targets C++17). __popcnt64 is MSVC's compiler intrinsic with the same
// semantics (population count of a 64-bit value), declared in <intrin.h>.
// Dependency-free on purpose -- included from perceptual-hash/finder code
// that has no other reason to pull in pybind11/OpenCV.
// ---------------------------------------------------------------------------

#include <cstdint>

#ifdef _MSC_VER
#include <intrin.h>
#endif

namespace base {

inline uint32_t popcount64(uint64_t v) {
#ifdef _MSC_VER
    return static_cast<uint32_t>(__popcnt64(v));
#else
    return static_cast<uint32_t>(__builtin_popcountll(v));
#endif
}

} // namespace base
