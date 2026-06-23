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
    src/bindings.cpp
    src/matching.cpp
    src/bundle_adjust.cpp
    src/validation.cpp
    src/canvas.cpp
    src/seam.cpp
    src/compositing.cpp
    src/exposure.cpp
    src/frame_selection.cpp
    src/wave_correct.cpp
    src/fg_register.cpp
    src/sr_classical.cpp
)

target_include_directories(batch PRIVATE
    include/
    ${OpenCV_INCLUDE_DIRS}
    ${EIGEN3_INCLUDE_DIR}
    ${eigen_SOURCE_DIR}
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
