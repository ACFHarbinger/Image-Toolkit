# ---------------------------------------------------------------------------
# base/benchmarks/CMakeLists.txt
#
# Builds Google Benchmark executables for the base C++ extension.
# Framework: google/benchmark (fetched automatically via FetchContent).
#
# Usage (from the project build directory):
#   cmake --build build/base --target base_bench_core
#   cmake --build build/base --target base_bench_math
#   cmake --build build/base --target base_bench_image
#   cmake --build build/base --target base_bench_finder
#   # or build all benchmarks at once:
#   cmake --build build/base --target base_benchmarks
#
# Run a benchmark binary (from build/base/benchmarks/):
#   ./base_bench_core --benchmark_format=json --benchmark_out=results.json
#
# Opt-in from the parent CMakeLists.txt with:
#   cmake -DBASE_BUILD_BENCHMARKS=ON ...
# ---------------------------------------------------------------------------

cmake_minimum_required(VERSION 3.18)

# ---------------------------------------------------------------------------
# Google Benchmark (header + runtime library)
# ---------------------------------------------------------------------------
include(FetchContent)

FetchContent_Declare(
    googlebenchmark
    GIT_REPOSITORY https://github.com/google/benchmark.git
    GIT_TAG        v1.8.5
    GIT_SHALLOW    TRUE
)
# Disable building benchmark's own tests to keep configuration fast
set(BENCHMARK_ENABLE_TESTING   OFF CACHE BOOL "" FORCE)
set(BENCHMARK_ENABLE_GTEST_TESTS OFF CACHE BOOL "" FORCE)
set(BENCHMARK_ENABLE_INSTALL   OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googlebenchmark)

# ---------------------------------------------------------------------------
# Inherit optional deps that may have been declared by the parent
# ---------------------------------------------------------------------------
if(NOT DEFINED cpp_httplib_SOURCE_DIR)
    FetchContent_Declare(
        cpp_httplib
        GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
        GIT_TAG        v0.18.0
        GIT_SHALLOW    TRUE
    )
    FetchContent_Declare(
        nlohmann_json
        GIT_REPOSITORY https://github.com/nlohmann/json.git
        GIT_TAG        v3.11.3
        GIT_SHALLOW    TRUE
    )
    FetchContent_MakeAvailable(cpp_httplib nlohmann_json)
endif()

# ---------------------------------------------------------------------------
# bench_impl — static library containing the C++ sources being benchmarked.
# Mirrors base/tests/CMakeLists.txt:base_impl but limited to modules that
# are actually exercised by the benchmarks (faster link, no Python embed).
# ---------------------------------------------------------------------------
add_library(bench_impl STATIC
    # Core: filesystem, conversion, merging, duplicate finder
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/core/convert.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/core/filesystem.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/core/finder.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/core/merger.cpp

    # Image I/O: batch load + filesystem scan
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/image/image_batch.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/image/scan_files.cpp

    # Math bindings (header-only math; .cpp supplies pybind11 wrappers
    # but the headers are used directly in bench_math.cpp)
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/math/math_bindings.cpp
)

# BATCH_TESTS suppresses pybind11 module-entry-point guards that assume a
# running Python interpreter (same flag used by the tests/ build).
target_compile_definitions(bench_impl PUBLIC BATCH_TESTS=1)

target_include_directories(bench_impl PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${OpenCV_INCLUDE_DIRS}
    ${EIGEN3_INCLUDE_DIR}
    ${eigen_SOURCE_DIR}
    ${pybind11_INCLUDE_DIRS}
    ${cpp_httplib_SOURCE_DIR}
    ${nlohmann_json_SOURCE_DIR}/include
)

target_link_libraries(bench_impl PUBLIC
    ${OpenCV_LIBS}
    Eigen3::Eigen
    OpenMP::OpenMP_CXX
)

if(OpenSSL_FOUND OR OPENSSL_FOUND)
    target_compile_definitions(bench_impl PUBLIC HAVE_OPENSSL=1)
    target_link_libraries(bench_impl PUBLIC OpenSSL::Crypto)
endif()

if(FFTW3_FOUND)
    target_link_libraries(bench_impl PUBLIC ${FFTW3_LIBRARIES})
    target_compile_definitions(bench_impl PUBLIC HAVE_FFTW3=1)
endif()

# ---------------------------------------------------------------------------
# Helper macro — define a benchmark executable with common settings
# ---------------------------------------------------------------------------
macro(add_base_benchmark TARGET_NAME SOURCE_FILE)
    add_executable(${TARGET_NAME} ${SOURCE_FILE})

    target_include_directories(${TARGET_NAME} PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/../include
        ${OpenCV_INCLUDE_DIRS}
        ${EIGEN3_INCLUDE_DIR}
        ${eigen_SOURCE_DIR}
        ${pybind11_INCLUDE_DIRS}
    )

    target_link_libraries(${TARGET_NAME} PRIVATE
        bench_impl
        benchmark::benchmark
        benchmark::benchmark_main
        ${OpenCV_LIBS}
        Eigen3::Eigen
        OpenMP::OpenMP_CXX
    )

    # Emit the benchmark binary to build/base/benchmarks/ for easy discovery
    set_target_properties(${TARGET_NAME} PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/benchmarks"
    )
endmacro()

# ---------------------------------------------------------------------------
# Individual benchmark executables
# ---------------------------------------------------------------------------

# 1. Filesystem / core operations (scan, delete, convert, merge)
add_base_benchmark(base_bench_core  bench_core.cpp)

# 2. Pure math library (distance, stats, information theory, graph, PCA)
add_base_benchmark(base_bench_math  bench_math.cpp)

# 3. Parallel image batch loading and thumbnailing (OpenCV + OpenMP)
add_base_benchmark(base_bench_image bench_image.cpp)

# 4. Duplicate / perceptual-hash image finder
add_base_benchmark(base_bench_finder bench_finder.cpp)

# ---------------------------------------------------------------------------
# Convenience umbrella target that builds all benchmarks
# ---------------------------------------------------------------------------
add_custom_target(base_benchmarks
    DEPENDS
        base_bench_core
        base_bench_math
        base_bench_image
        base_bench_finder
    COMMENT "Build all base C++ benchmark executables"
)
