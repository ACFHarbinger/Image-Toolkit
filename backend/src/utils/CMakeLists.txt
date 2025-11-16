cmake_minimum_required(VERSION 3.16)
project(ArgParserLib CXX)

# Set the required C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# --- Find cxxopts (Header-only library) ---
# This step locates the header file for the argument parser library.
find_path(CXXOPTS_INCLUDE_DIR cxxopts.hpp
    PATHS 
    /usr/include
    /usr/local/include
    # Add a fallback for local dependencies
    ${CMAKE_SOURCE_DIR}/third_party/cxxopts/include
)
if (NOT CXXOPTS_INCLUDE_DIR)
    message(FATAL_ERROR "cxxopts.hpp not found. Argument parsing requires cxxopts.")
endif()

# Add necessary include paths for both cxxopts and your local headers (like Definitions.h)
include_directories(${CXXOPTS_INCLUDE_DIR})
include_directories(${CMAKE_SOURCE_DIR}) 

# --- Build the Library ---

# Create a static library containing the argument parser implementation
add_library(ArgParserLib STATIC
    ArgParser.cpp
)

# Since cxxopts is header-only, no explicit library linking is needed beyond 
# system requirements (which are usually covered by default for static libs).