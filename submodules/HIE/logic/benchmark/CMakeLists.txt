find_package(benchmark QUIET)
if(NOT benchmark_FOUND)
    include(FetchContent)
    FetchContent_Declare(
        googlebenchmark
        URL https://github.com/google/benchmark/archive/refs/tags/v1.9.0.zip
    )
    set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(googlebenchmark)
endif()

add_executable(hybrid_image_editor_benchmark greet_benchmark.cpp solvers_benchmark.cpp)
target_link_libraries(hybrid_image_editor_benchmark PRIVATE hybrid_image_editor_logic benchmark::benchmark_main)
