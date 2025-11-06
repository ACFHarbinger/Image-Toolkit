# Set the minimum required version of CMake.
# Version 3.12 is a good modern default, supporting C++17 features.
cmake_minimum_required(VERSION 3.12)

# Define the project name
project(ImageToolkit LANGUAGES CXX)

# --- C++ Standard ---
# We must use C++17 to get access to std::filesystem
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# --- Find Required Dependencies ---
# CImg requires external libraries to load/save JPEG and PNG files.
# We must find them on the system.
find_package(JPEG REQUIRED)
find_package(PNG REQUIRED)

# --- Define the Library ---
# We are creating a static library named "ImageToolkitCore"
add_library(ImageToolkitCore STATIC
    src/core/FileSystemEntries.cpp
    src/core/FormatConverter.cpp
    src/core/ImageMerger.cpp
)

# --- Include Directories ---
# Tell the library where to find its own headers (like FileSystemEntries.h)
# and the CImg.h header.
target_include_directories(ImageToolkitCore PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src/core
)

# --- Link Libraries ---
# Link our library against the dependencies we found.
target_link_libraries(ImageToolkitCore PUBLIC
    # Link JPEG and PNG libraries
    JPEG::JPEG
    PNG::PNG

    # Link stdc++fs for std::filesystem compatibility
    # This is needed for older compilers (like GCC < 9)
    stdc++fs
)

# --- Optional: Create an Executable (Example) ---
# If you later create a "main.cpp" to run your tool, you would
# uncomment the lines below.

# add_executable(ImageToolkitApp src/main.cpp)
# target_link_libraries(ImageToolkitApp PRIVATE ImageToolkitCore)