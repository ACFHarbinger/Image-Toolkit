cmake_minimum_required(VERSION 3.20)
project(single_module_template LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(BUILD_TESTING "Build tests" OFF)
option(BUILD_BENCHMARK "Build benchmarks" OFF)

add_library(single_module_template_lib STATIC
    src/greet.cpp
)
target_include_directories(single_module_template_lib PUBLIC include)

add_executable(single_module_template_cli src/main.cpp)
target_link_libraries(single_module_template_cli PRIVATE single_module_template_lib)

if(BUILD_TESTING)
    enable_testing()
    add_subdirectory(test)
endif()

if(BUILD_BENCHMARK)
    add_subdirectory(benchmark)
endif()
