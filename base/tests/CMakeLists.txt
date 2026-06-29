# ---------------------------------------------------------------------------
# base/tests/CMakeLists.txt
#
# Builds the native C++ unit test binary for the base extension using
# Catch2 v3 (fetched automatically via FetchContent).
#
# Usage:
#   cmake --build build/base --target base_tests
#   ctest --test-dir build/base -V
# or equivalently:
#   just test-base-cpp
# ---------------------------------------------------------------------------

include(FetchContent)

FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG        v3.7.1
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(Catch2)

# Phase 5: cpp-httplib + nlohmann/json (inherited from parent if already declared)
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
# Shared object library: all base implementation sources (without pybind11
# entry point) so the test binary can link them directly without Python.
# ---------------------------------------------------------------------------
add_library(base_impl OBJECT
    # Animation / Anime Stitch Pipeline submodules
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/animation/matching.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/animation/bundle_adjust.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/animation/validation.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/animation/canvas.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/animation/seam.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/animation/compositing.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/animation/exposure.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/animation/frame_selection.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/animation/wave_correct.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/animation/fg_register.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/animation/sr_classical.cpp

    # Image I/O + filesystem (Phase 2)
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/image/image_batch.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/image/scan_files.cpp

    # Video thumbnails (Phase 3)
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/video/video_batch.cpp

    # Secure vector database (Phase 4)
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/secret/locked_secret.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/secret/vault_db.cpp

    # HTTP request sequencing (Phase 5)
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/web/web_requests.cpp
)

# The implementation files include pybind11 headers only to get
# py::array_t and related types.  We need pybind11 headers in the include
# path but do NOT link the pybind11 module entry point.
target_include_directories(base_impl PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${OpenCV_INCLUDE_DIRS}
    ${EIGEN3_INCLUDE_DIR}
    ${pybind11_INCLUDE_DIRS}
    ${cpp_httplib_SOURCE_DIR}
    ${nlohmann_json_SOURCE_DIR}/include
)

if(SQLCIPHER_FOUND AND SODIUM_FOUND)
    target_include_directories(base_impl PUBLIC ${SQLCIPHER_INCLUDE_DIRS} ${SODIUM_INCLUDE_DIRS})
    target_link_libraries(base_impl PUBLIC ${SQLCIPHER_LIBRARIES} ${SODIUM_LIBRARIES})
    target_compile_definitions(base_impl PUBLIC HAVE_SQLCIPHER=1)
endif()

target_link_libraries(base_impl PUBLIC
    ${OpenCV_LIBS}
    Eigen3::Eigen
    OpenMP::OpenMP_CXX
)

target_compile_definitions(base_impl PUBLIC BATCH_TESTS=1)

if(FFTW3_FOUND)
    target_link_libraries(base_impl PUBLIC ${FFTW3_LIBRARIES})
    target_compile_definitions(base_impl PUBLIC HAVE_FFTW3=1)
endif()

# ---------------------------------------------------------------------------
# Test executable
# ---------------------------------------------------------------------------
add_executable(base_tests
    # Animation tests
    animation/test_seam.cpp
    animation/test_compositing.cpp
    animation/test_bundle_adjust.cpp
    animation/test_exposure.cpp
    animation/test_matching.cpp
    animation/test_validation.cpp
    animation/test_wave_correct.cpp
    animation/test_fuzz.cpp

    # Image I/O + filesystem tests (Phase 2)
    image/test_image_batch.cpp

    # Video thumbnail tests (Phase 3)
    video/test_video_batch.cpp

    # Secure vector database tests (Phase 4)
    secret/test_vault_db.cpp
    secret/test_vault_security.cpp

    # HTTP tests (Phase 5)
    web/test_web_requests.cpp

    # Math library tests (Phase 6)
    math/test_math.cpp
)

target_include_directories(base_tests PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
    ${OpenCV_INCLUDE_DIRS}
    ${EIGEN3_INCLUDE_DIR}
    ${eigen_SOURCE_DIR}
    ${pybind11_INCLUDE_DIRS}
    ${cpp_httplib_SOURCE_DIR}
    ${nlohmann_json_SOURCE_DIR}/include
)

target_link_libraries(base_tests PRIVATE
    base_impl
    Catch2::Catch2WithMain
    pybind11::embed
)

# Register with CTest
include(Catch)
catch_discover_tests(base_tests)
