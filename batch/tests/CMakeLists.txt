# ---------------------------------------------------------------------------
# batch/tests/CMakeLists.txt
#
# Builds the native C++ unit test binary for the batch extension using
# Catch2 v3 (fetched automatically via FetchContent).
#
# Usage:
#   cmake --build build/batch --target batch_tests
#   ctest --test-dir build/batch -V
# or equivalently:
#   just test-batch-cpp
# ---------------------------------------------------------------------------

include(FetchContent)

FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG        v3.7.1
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(Catch2)

# ---------------------------------------------------------------------------
# Shared object library: all batch implementation sources (without pybind11
# entry point) so the test binary can link them directly without Python.
# ---------------------------------------------------------------------------
add_library(batch_impl OBJECT
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/matching.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/bundle_adjust.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/validation.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/canvas.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/seam.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/compositing.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/exposure.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/frame_selection.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/wave_correct.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/fg_register.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/sr_classical.cpp
)

# The implementation files include pybind11 headers only to get
# py::array_t and related types.  We need pybind11 headers in the include
# path but do NOT link the pybind11 module entry point.
target_include_directories(batch_impl PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${OpenCV_INCLUDE_DIRS}
    ${EIGEN3_INCLUDE_DIR}
    ${pybind11_INCLUDE_DIRS}
)

target_link_libraries(batch_impl PUBLIC
    ${OpenCV_LIBS}
    Eigen3::Eigen
    OpenMP::OpenMP_CXX
)

if(FFTW3_FOUND)
    target_link_libraries(batch_impl PUBLIC ${FFTW3_LIBRARIES})
    target_compile_definitions(batch_impl PUBLIC HAVE_FFTW3=1)
endif()

# ---------------------------------------------------------------------------
# Test executable
# ---------------------------------------------------------------------------
add_executable(batch_tests
    test_seam.cpp
    test_compositing.cpp
    test_bundle_adjust.cpp
    test_exposure.cpp
    test_matching.cpp
    test_fuzz.cpp
)

target_include_directories(batch_tests PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${OpenCV_INCLUDE_DIRS}
    ${EIGEN3_INCLUDE_DIR}
    ${pybind11_INCLUDE_DIRS}
)

target_link_libraries(batch_tests PRIVATE
    batch_impl
    Catch2::Catch2WithMain
)

# Register with CTest
include(Catch)
catch_discover_tests(batch_tests)
