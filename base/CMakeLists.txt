cmake_minimum_required(VERSION 3.18)
project(base CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---------------------------------------------------------------------------
# Required dependencies
# ---------------------------------------------------------------------------
find_package(OpenCV 4.8 REQUIRED
    COMPONENTS core imgproc imgcodecs videoio stitching features2d video photo)
# Fetch Eigen3 unconditionally if not on system path (usually missing in isolated envs)
include(FetchContent)
FetchContent_Declare(
    eigen
    GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
    GIT_TAG        3.4.0
)
FetchContent_MakeAvailable(eigen)

find_package(pybind11 QUIET)
if(NOT pybind11_FOUND)
    message(STATUS "pybind11 not found locally, downloading via FetchContent...")
    FetchContent_Declare(
        pybind11
        GIT_REPOSITORY https://github.com/pybind/pybind11.git
        GIT_TAG        v2.11.1
    )
    FetchContent_MakeAvailable(pybind11)
endif()

# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------
find_package(PkgConfig QUIET)
if(PkgConfig_FOUND)
    pkg_check_modules(FFTW3 QUIET fftw3)   # for sr_classical.cpp DCT/FFT
endif()
find_package(CUDA QUIET)                    # for GPU-accelerated compositing
find_package(OpenMP REQUIRED)              # for parallel pixel loops

# ---------------------------------------------------------------------------
# Phase 4: SQLCipher + libsodium (optional — base::secret full implementation)
# ---------------------------------------------------------------------------
if(PkgConfig_FOUND)
    pkg_check_modules(SQLCIPHER QUIET sqlcipher)
    pkg_check_modules(SODIUM    QUIET libsodium)
endif()
if(SQLCIPHER_FOUND AND SODIUM_FOUND)
    message(STATUS "base: SQLCipher + libsodium found — base::secret fully enabled")
    add_compile_definitions(HAVE_SQLCIPHER=1)
else()
    message(STATUS "base: SQLCipher or libsodium not found — base::secret will use stubs")
endif()

# ---------------------------------------------------------------------------
# Phase 8: OpenSSL (optional — for SHA-256 in finder.cpp)
# Falls back to inline FIPS 180-4 implementation if not found.
# ---------------------------------------------------------------------------
find_package(OpenSSL QUIET)
if(OpenSSL_FOUND OR OPENSSL_FOUND)
    message(STATUS "base: OpenSSL found — SHA-256 via EVP API")
    add_compile_definitions(HAVE_OPENSSL=1)
else()
    message(STATUS "base: OpenSSL NOT found — using inline SHA-256 fallback")
endif()

# ---------------------------------------------------------------------------
# Phase 5: cpp-httplib + nlohmann/json (header-only, auto-fetched via FetchContent)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Optional: OpenCV ximgproc (SLIC for fg_register)
# ---------------------------------------------------------------------------
find_package(OpenCV QUIET COMPONENTS ximgproc)
if(OpenCV_ximgproc_FOUND OR TARGET opencv_ximgproc)
    add_compile_definitions(HAVE_OPENCV_XIMGPROC=1)
    message(STATUS "base: OpenCV ximgproc found — SLIC support enabled")
else()
    message(STATUS "base: OpenCV ximgproc NOT found — SLIC will use Python fallback")
endif()

# ---------------------------------------------------------------------------
# Compiler flags
# ---------------------------------------------------------------------------
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -ffast-math")
if(OpenMP_FOUND)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OpenMP_CXX_FLAGS}")
endif()

# ---------------------------------------------------------------------------
# base extension module
# ---------------------------------------------------------------------------
pybind11_add_module(base
    # Module entry point
    src/bindings.cpp

    # Animation / Anime Stitch Pipeline submodules (Phase 1–6, complete)
    src/animation/matching.cpp
    src/animation/bundle_adjust.cpp
    src/animation/validation.cpp
    src/animation/canvas.cpp
    src/animation/seam.cpp
    src/animation/compositing.cpp
    src/animation/exposure.cpp
    src/animation/frame_selection.cpp
    src/animation/wave_correct.cpp
    src/animation/fg_register.cpp
    src/animation/sr_classical.cpp

    # Image I/O + filesystem (Phase 2)
    src/image/image_batch.cpp
    src/image/scan_files.cpp

    # Video thumbnails (Phase 3)
    src/video/video_batch.cpp

    # Secure vector database (Phase 4)
    src/secret/locked_secret.cpp
    src/secret/vault_db.cpp

    # HTTP + board crawlers + cloud sync (Phase 5 + 9)
    # clients/: single-concept HTTP files
    src/web/clients/web_requests.cpp
    src/web/clients/image_crawler.cpp
    src/web/clients/reverse_image_search.cpp
    # board crawlers: orchestrator includes include/web/crawlers/{danbooru,gelbooru,sankaku}.hpp
    src/web/board_crawler.cpp
    # cloud sync: orchestrator includes include/web/cloud/{dropbox,google_drive,onedrive}_sync.hpp
    src/web/cloud_sync.cpp

    # Phase 8: core (image/video conversion, filesystem, finder, merger, wallpaper)
    src/core/convert.cpp
    src/core/filesystem.cpp
    src/core/finder.cpp
    src/core/merger.cpp
    src/core/wallpaper.cpp

    # Phase 10: utils (migration, slideshow daemon)
    src/utils/migration.cpp
    src/utils/slideshow.cpp

    # Phase 11: math bindings
    src/math/math_bindings.cpp
)

target_include_directories(base PRIVATE
    include/
    ${OpenCV_INCLUDE_DIRS}
    ${EIGEN3_INCLUDE_DIR}
    ${eigen_SOURCE_DIR}
    ${pybind11_INCLUDE_DIRS}
    ${cpp_httplib_SOURCE_DIR}
    ${nlohmann_json_SOURCE_DIR}/include
)

target_link_libraries(base PRIVATE
    ${OpenCV_LIBS}
    Eigen3::Eigen
    OpenMP::OpenMP_CXX
)

if(FFTW3_FOUND)
    target_include_directories(base PRIVATE ${FFTW3_INCLUDE_DIRS})
    target_link_libraries(base PRIVATE ${FFTW3_LIBRARIES})
    target_compile_definitions(base PRIVATE HAVE_FFTW3=1)
    message(STATUS "base: FFTW3 found — fast DCT/FFT enabled")
else()
    message(STATUS "base: FFTW3 NOT found — using cv::dft (BSD) fallback")
endif()

if(CUDA_FOUND)
    target_compile_definitions(base PRIVATE HAVE_CUDA=1)
    message(STATUS "base: CUDA found — GPU paths enabled")
endif()

if(SQLCIPHER_FOUND AND SODIUM_FOUND)
    target_include_directories(base PRIVATE ${SQLCIPHER_INCLUDE_DIRS} ${SODIUM_INCLUDE_DIRS})
    target_link_libraries(base PRIVATE ${SQLCIPHER_LIBRARIES} ${SODIUM_LIBRARIES})
endif()

if(OpenSSL_FOUND OR OPENSSL_FOUND)
    target_link_libraries(base PRIVATE OpenSSL::Crypto)
endif()

# ---------------------------------------------------------------------------
# Install alongside base.so in the Python animation package
# ---------------------------------------------------------------------------
install(TARGETS base DESTINATION backend/src/animation/)

# ---------------------------------------------------------------------------
# Native C++ unit tests (Catch2 v3, opt-in)
# Enable with: cmake -DBASE_BUILD_TESTS=ON ...
# ---------------------------------------------------------------------------
option(BASE_BUILD_TESTS "Build native C++ unit tests for base" ON)
if(BASE_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
