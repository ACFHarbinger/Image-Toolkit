cmake_minimum_required(VERSION 3.20)
project(hybrid_image_editor LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(BUILD_TESTING     "Build tests"      OFF)
option(BUILD_BENCHMARK   "Build benchmarks" OFF)
option(HIE_ENABLE_SIMD_SEAM "Compile solve_seam's DP row fill with AVX2 (x86) / NEON (ARM) vectorization" OFF)

# ─── Core Logic Library ────────────────────────────────────────────────────────
add_library(hybrid_image_editor_logic STATIC
    logic/src/greet.cpp
    logic/src/render_graph.cpp
    logic/src/exact_solvers.cpp
    logic/src/metaheuristics.cpp
)
target_include_directories(hybrid_image_editor_logic PUBLIC logic/include)

# HIE_ENABLE_SIMD_SEAM is opt-in and scoped to exact_solvers.cpp alone (not a
# blanket -march=native on the whole target) so the default build stays
# portable to CPUs without AVX2. Only x86/x86_64 needs an explicit -mavx2
# -mfma flag; AArch64 has NEON as a baseline ISA feature, so no extra flag is
# added there (32-bit ARM without NEON is not a supported target for this
# option).
if(HIE_ENABLE_SIMD_SEAM)
    # PUBLIC (not PRIVATE): logic/test/test_solvers.cpp needs to see this
    # definition too, to compile its SIMD-vs-scalar-reference comparison test.
    target_compile_definitions(hybrid_image_editor_logic PUBLIC HIE_ENABLE_SIMD_SEAM)
    if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|amd64|AMD64|i.86)$")
        set_source_files_properties(logic/src/exact_solvers.cpp PROPERTIES
            COMPILE_OPTIONS "-mavx2;-mfma")
    endif()
endif()

# ─── CLI Entry Point ──────────────────────────────────────────────────────────
add_executable(hybrid_image_editor_cli logic/src/main.cpp)
target_link_libraries(hybrid_image_editor_cli PRIVATE hybrid_image_editor_logic)

# ─── Tests ────────────────────────────────────────────────────────────────────
if(BUILD_TESTING)
    enable_testing()
    add_subdirectory(logic/test)
endif()

# ─── Benchmarks ───────────────────────────────────────────────────────────────
if(BUILD_BENCHMARK)
    add_subdirectory(logic/benchmark)
endif()
