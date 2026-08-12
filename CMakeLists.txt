cmake_minimum_required(VERSION 3.20)
project(hybrid_image_editor LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(BUILD_TESTING   "Build tests"      OFF)
option(BUILD_BENCHMARK "Build benchmarks" OFF)

# ─── Core Logic Library ────────────────────────────────────────────────────────
add_library(hybrid_image_editor_logic STATIC
    logic/src/greet.cpp
    logic/src/render_graph.cpp
    logic/src/exact_solvers.cpp
    logic/src/metaheuristics.cpp
)
target_include_directories(hybrid_image_editor_logic PUBLIC logic/include)

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
