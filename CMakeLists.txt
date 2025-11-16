cmake_minimum_required(VERSION 3.16)
project(ImageToolkit_Parent CXX)

# Set the required C++ standard for the entire project
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Enable CTest integration for test discovery
enable_testing()

# --- 1. FIND TOP-LEVEL DEPENDENCIES (Needed by multiple subdirectories) ---
# Finding these at the root ensures consistent versions across sub-projects.
find_package(GTest REQUIRED)
find_package(PkgConfig REQUIRED)
find_package(OpenCV REQUIRED)
find_package(CURL REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(JNI REQUIRED)
# Note: Other dependencies like libpqxx, Gumbo, nlohmann/json, and cxxopts 
# should be found by PkgConfig or find_path in the subdirectories.

# --- 2. ADD SUBDIRECTORIES FOR BUILDING CORE COMPONENTS ---

# Directory for Core Image and File System Utilities
add_subdirectory(app/src/core)

# Directory for Web-related components (WebClient, GoogleDriveSync)
add_subdirectory(app/src/web)

# Directory for Utility components (ArgParser, Definitions)
add_subdirectory(app/src/utils)

# --- 3. ADD SUBDIRECTORY FOR TESTS ---
# This directory will execute the provided CMakeLists.txt (or a similar one)
# to compile all test executables and register them with CTest.
add_subdirectory(app/test)