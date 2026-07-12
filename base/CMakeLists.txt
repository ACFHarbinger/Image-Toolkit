cmake_minimum_required(VERSION 3.18)

# Suppress deprecation warnings from older dependencies (pybind11, Eigen, FindCUDA)
if(POLICY CMP0146)
    cmake_policy(SET CMP0146 OLD)
endif()
if(POLICY CMP0148)
    cmake_policy(SET CMP0148 OLD)
endif()
if(POLICY CMP0167)
    cmake_policy(SET CMP0167 OLD)
endif()

# Set as default so it propagates to FetchContent subdirectories
set(CMAKE_POLICY_DEFAULT_CMP0146 OLD)
set(CMAKE_POLICY_DEFAULT_CMP0148 OLD)
set(CMAKE_POLICY_DEFAULT_CMP0167 OLD)

project(base CXX)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---------------------------------------------------------------------------
# Required dependencies
# ---------------------------------------------------------------------------
find_package(OpenCV 4.6 REQUIRED
    COMPONENTS core imgproc imgcodecs videoio stitching features2d video photo)
# Fetch Eigen3 unconditionally if not on system path (usually missing in isolated envs)
include(FetchContent)
find_package(Eigen3 QUIET)
if(NOT Eigen3_FOUND)
    FetchContent_Declare(
        eigen
        GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
        GIT_TAG 3.4.0
    )
    FetchContent_MakeAvailable(eigen)
endif()

set(PYBIND11_FINDPYTHON ON)
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

if(NOT SQLCIPHER_FOUND)
    find_path(SQLCIPHER_INCLUDE_DIR NAMES sqlcipher/sqlite3.h sqlite3.h PATHS /usr/include /usr/local/include /usr/include/sqlcipher)
    find_library(SQLCIPHER_LIBRARY NAMES sqlcipher libsqlcipher PATHS /usr/lib /usr/lib/x86_64-linux-gnu /usr/local/lib)
    if(SQLCIPHER_INCLUDE_DIR AND SQLCIPHER_LIBRARY)
        set(SQLCIPHER_FOUND TRUE)
        set(SQLCIPHER_INCLUDE_DIRS ${SQLCIPHER_INCLUDE_DIR})
        set(SQLCIPHER_LIBRARIES ${SQLCIPHER_LIBRARY})
    endif()
endif()

if(NOT SODIUM_FOUND)
    find_path(SODIUM_INCLUDE_DIR NAMES sodium.h PATHS "$ENV{CONDA_PREFIX}/include" /usr/include /usr/local/include)
    find_library(SODIUM_LIBRARY NAMES sodium libsodium PATHS "$ENV{CONDA_PREFIX}/lib" /usr/lib /usr/lib/x86_64-linux-gnu /usr/local/lib)
    if(SODIUM_INCLUDE_DIR AND SODIUM_LIBRARY)
        set(SODIUM_FOUND TRUE)
        set(SODIUM_INCLUDE_DIRS ${SODIUM_INCLUDE_DIR})
        set(SODIUM_LIBRARIES ${SODIUM_LIBRARY})
    endif()
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

# ---------------------------------------------------------------------------
# Compiler flags
# ---------------------------------------------------------------------------
set(CMAKE_CXX_FLAGS_RELEASE "-O2")
if(OpenMP_FOUND)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OpenMP_CXX_FLAGS}")
endif()

# ---------------------------------------------------------------------------
# base extension module
# ---------------------------------------------------------------------------
add_subdirectory(vendor/argon2)

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
    src/animation/fg_register.cpp

    # Image I/O + filesystem (Phase 2)
    src/image/image_batch.cpp
    src/image/scan_files.cpp

    # Video thumbnails (Phase 3)
    src/video/video_batch.cpp

    # Secure vector database (Phase 4)
    src/secret/locked_secret.cpp
    src/secret/vault_db.cpp

    # Unified Library Database engine (Phase DB)
    src/database/database.cpp

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

    # Similarity Finder engine (hashing, VP-tree, HNSW, SSIM/features, diff)
    src/core/similarity/hashing.cpp
    src/core/similarity/vptree.cpp
    src/core/similarity/hnsw.cpp
    src/core/similarity/visual.cpp
    src/core/similarity/bindings.cpp

    # Entity Recon data/discovery engine (HNSW identity index + cutout hashing)
    src/web/recon/identity_index.cpp
    src/web/recon/bindings.cpp

    # Reverse-search ROI preprocessing (crop + saliency auto-crop)
    src/web/roi/roi_processor.cpp
    src/web/roi/bindings.cpp

    # Phase 10: utils (migration, slideshow daemon)
    src/utils/migration.cpp
    src/utils/slideshow.cpp
    src/utils/monitor_slideshow.cpp

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


if(CUDA_FOUND)
    target_compile_definitions(base PRIVATE HAVE_CUDA=1)
    message(STATUS "base: CUDA found — GPU paths enabled")
endif()

if(SQLCIPHER_FOUND AND SODIUM_FOUND)
    target_include_directories(base PRIVATE ${SQLCIPHER_INCLUDE_DIRS} ${SODIUM_INCLUDE_DIRS} /usr/include /usr/include/sqlcipher)
    target_link_libraries(base PRIVATE sqlcipher sodium argon2)
    # pixi lib dir must precede /usr/lib in the RPATH: old-style RPATH resolves
    # transitively, and pixi's libssl needs pixi's libcrypto (not the system one).
    # An explicit -rpath link option lands before CMake's auto-generated entries.
    # --enable-new-dtags forces RUNPATH (not legacy RPATH) generation: an
    # old-style RPATH on this MODULE-type target gets appended to the dynamic
    # linker's *global* search path for the whole process, hijacking unrelated
    # libraries loaded later by PySide6/Qt. Verify with `readelf -d base.so`
    # — must say RUNPATH, never RPATH.
    target_link_options(base PRIVATE
        "-Wl,-rpath,${CMAKE_CURRENT_SOURCE_DIR}/../.pixi/envs/default/lib"
        "-Wl,--enable-new-dtags")
    target_link_directories(base PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../.pixi/envs/default/lib /usr/lib/x86_64-linux-gnu)
endif()

if(OpenSSL_FOUND OR OPENSSL_FOUND)
    target_link_libraries(base PRIVATE OpenSSL::Crypto)
endif()

# ---------------------------------------------------------------------------
# Install alongside base.so in the Python root directory
# ---------------------------------------------------------------------------
install(TARGETS base DESTINATION .)

# ---------------------------------------------------------------------------
# Native C++ unit tests (Catch2 v3, opt-in)
# Enable with: cmake -DBASE_BUILD_TESTS=ON ...
# ---------------------------------------------------------------------------
option(BASE_BUILD_TESTS "Build native C++ unit tests for base" ON)
if(BASE_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# ---------------------------------------------------------------------------
# Native C++ benchmarks (Google Benchmark, opt-in)
# Enable with: cmake -DBASE_BUILD_BENCHMARKS=ON ..
# ---------------------------------------------------------------------------
option(BASE_BUILD_BENCHMARKS "Build native C++ benchmarks for base" OFF)
if(BASE_BUILD_BENCHMARKS)
    add_subdirectory(benchmarks)
endif()
