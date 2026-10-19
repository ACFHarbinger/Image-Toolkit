# env/cpp/CMakeLists.txt
# CMake configuration file for building C++ projects.

cmake_minimum_required(VERSION 3.17)
project(PolyglotCppApp VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Qt GUI dependencies
find_package(Qt5 COMPONENTS Core Gui Widgets Required)

# Define executable
add_executable(PolyglotCppApp main.cpp)

# Link dependencies
target_link_libraries(PolyglotCppApp PRIVATE Qt5::Widgets)
