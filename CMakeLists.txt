cmake_minimum_required(VERSION 3.16)

# Main project name
project(ImageToolSuite LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# --- Common Dependency Finding ---
# We perform dependency finding at the root level to avoid redundant calls 
# and ensure consistency across subdirectories.

# Image Processing
find_package(OpenCV REQUIRED) 
# Cryptography
find_package(OpenSSL REQUIRED)
# Java/Kotlin Interop
find_package(JNI REQUIRED)
# JSON Serialization
find_package(nlohmann_json REQUIRED)
# PostgreSQL/libpqxx
find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBPQXX REQUIRED IMPORTED_TARGET libpqxx)
find_package(PostgreSQL REQUIRED)
# Machine learning
find_package(Torch REQUIRED)

# --- Add Subdirectories ---

# Directory 1: Core application logic (contains Core executable)
# This directory is assumed to contain the detailed CMakeLists.txt from the Canvas.
add_subdirectory(backend/src/core)

# Directory 2: Web-related modules (Placeholder)
# If this directory defines its own targets (e.g., a library or tests), 
# those will be included here.
add_subdirectory(backend/src/web)

# Directory 3: Machine learning models
add_subdirectory(backend/src/models)

# Directory 4: Utils classes
add_subdirectory(backend/src/utils)