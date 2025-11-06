# Set the minimum required version of CMake.
cmake_minimum_required(VERSION 3.12)

# Define the project name (this is the C++ sub-project)
project(ImageToolkitDesktop LANGUAGES CXX)
set(CMAKE_CURRENT_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/desktop")

# --- C++ Standard ---
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# --- Find Required Dependencies ---
find_package(JPEG REQUIRED)
find_package(PNG REQUIRED)

# --- Define the Library ---
# Use CMAKE_CURRENT_SOURCE_DIR to make paths absolute
add_library(ImageToolkitCore STATIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src/core/FileSystemEntries.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/core/FormatConverter.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/core/ImageMerger.cpp
)

# Public include directories
target_include_directories(ImageToolkitCore PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src/core
)

# Link dependencies
target_link_libraries(ImageToolkitCore PUBLIC
    JPEG::JPEG
    PNG::PNG
)

# --- ADDITIONS FOR TESTING ---
enable_testing()

# Download and configure GoogleTest
include(FetchContent)

# FIX: Changed from a fragile URL download to a robust Git repository clone.
# This avoids the 404 errors you were seeing.
FetchContent_Declare(
  googlestest
  GIT_REPOSITORY https://github.com/google/googletest.git
  GIT_TAG        v1.17.0  # Use the correct tag name
)

FetchContent_MakeAvailable(googlestest)

# --- Define Test Executables ---
add_executable(FileSystemTests
    ${CMAKE_CURRENT_SOURCE_DIR}/test/TestFileSystemEntries.cpp
)
target_link_libraries(FileSystemTests PRIVATE
    ImageToolkitCore
    gtest_main
)
add_test(NAME FileSystemEntriesTests COMMAND FileSystemTests)

add_executable(ImageConverterTests
    ${CMAKE_CURRENT_SOURCE_DIR}/test/TestImageFormatConverter.cpp
)
target_link_libraries(ImageConverterTests PRIVATE
    ImageToolkitCore
    gtest_main
)
add_test(NAME ImageFormatConverterTests COMMAND ImageConverterTests)

add_executable(ImageMergerTests
    ${CMAKE_CURRENT_SOURCE_DIR}/test/TestImageMerger.cpp
)
target_link_libraries(ImageMergerTests PRIVATE
    ImageToolkitCore
    gtest_main
)
add_test(NAME ImageMergerTests COMMAND ImageMergerTests)

include(GoogleTest)