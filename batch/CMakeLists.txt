cmake_minimum_required(VERSION 3.18)
project(batch CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---------------------------------------------------------------------------
# Required dependencies
# ---------------------------------------------------------------------------
find_package(OpenCV 4.8 REQUIRED
    COMPONENTS core imgproc stitching features2d video)
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
find_package(CUDA QUIET)                    # for GPU-accelerated compositing (Phase 6)
find_package(OpenMP REQUIRED)              # for parallel pixel loops

# ---------------------------------------------------------------------------
# Phase 4: SQLCipher + libsodium (optional — batch::secret full implementation)
# ---------------------------------------------------------------------------
if(PkgConfig_FOUND)
    pkg_check_modules(SQLCIPHER QUIET sqlcipher)
    pkg_check_modules(SODIUM    QUIET libsodium)
endif()
if(SQLCIPHER_FOUND AND SODIUM_FOUND)
    message(STATUS "batch: SQLCipher + libsodium found — batch::secret fully enabled")
    add_compile_definitions(HAVE_SQLCIPHER=1)
else()
    message(STATUS "batch: SQLCipher or libsodium not found — batch::secret will use stubs")
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
    message(STATUS "batch: OpenCV ximgproc found — SLIC support enabled")
else()
    message(STATUS "batch: OpenCV ximgproc NOT found — SLIC will use Python fallback")
endif()

# ---------------------------------------------------------------------------
# Compiler flags
# ---------------------------------------------------------------------------
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -ffast-math")
if(OpenMP_FOUND)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OpenMP_CXX_FLAGS}")
endif()

# ---------------------------------------------------------------------------
# batch extension module
# ---------------------------------------------------------------------------
pybind11_add_module(batch
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

    # Image I/O + filesystem (Phase 2 — skeleton)
    src/image/image_batch.cpp
    src/image/scan_files.cpp

    # Video thumbnails (Phase 3 — skeleton)
    src/video/video_batch.cpp

    # Secure vector database (Phase 4 — skeleton)
    src/secret/locked_secret.cpp
    src/secret/vault_db.cpp

    # HTTP request sequencing (Phase 5 — skeleton)
    src/web/web_requests.cpp
)

target_include_directories(batch PRIVATE
    include/
    ${OpenCV_INCLUDE_DIRS}
    ${EIGEN3_INCLUDE_DIR}
    ${eigen_SOURCE_DIR}
    ${pybind11_INCLUDE_DIRS}
    ${cpp_httplib_SOURCE_DIR}
    ${nlohmann_json_SOURCE_DIR}/include
)

target_link_libraries(batch PRIVATE
    ${OpenCV_LIBS}
    Eigen3::Eigen
    OpenMP::OpenMP_CXX
)

if(FFTW3_FOUND)
    target_include_directories(batch PRIVATE ${FFTW3_INCLUDE_DIRS})
    target_link_libraries(batch PRIVATE ${FFTW3_LIBRARIES})
    target_compile_definitions(batch PRIVATE HAVE_FFTW3=1)
    message(STATUS "batch: FFTW3 found — fast DCT/FFT enabled")
else()
    message(STATUS "batch: FFTW3 NOT found — using cv::dft (BSD) fallback")
endif()

if(CUDA_FOUND)
    target_compile_definitions(batch PRIVATE HAVE_CUDA=1)
    message(STATUS "batch: CUDA found — GPU paths enabled (Phase 6)")
endif()

if(SQLCIPHER_FOUND AND SODIUM_FOUND)
    target_include_directories(batch PRIVATE ${SQLCIPHER_INCLUDE_DIRS} ${SODIUM_INCLUDE_DIRS})
    target_link_libraries(batch PRIVATE ${SQLCIPHER_LIBRARIES} ${SODIUM_LIBRARIES})
endif()

# ---------------------------------------------------------------------------
# Install alongside base.so in the Python animation package
# ---------------------------------------------------------------------------
install(TARGETS batch DESTINATION backend/src/animation/)

# ---------------------------------------------------------------------------
# Native C++ unit tests (Catch2 v3, opt-in)
# Enable with: cmake -DBATCH_BUILD_TESTS=ON ...
# ---------------------------------------------------------------------------
option(BATCH_BUILD_TESTS "Build native C++ unit tests for batch" ON)
if(BATCH_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
