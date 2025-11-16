cmake_minimum_required(VERSION 3.16)
project(WebCoreLib CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# --- 1. Find PkgConfig (Tool for finding C/C++ libraries) ---
find_package(PkgConfig REQUIRED)

# --- 2. Find libcurl (For HTTP requests, replacing Python 'requests') ---
# libcurl is widely used and provides the foundation for our WebClient and DriveSync.
find_package(CURL REQUIRED)
if (NOT CURL_FOUND)
    message(FATAL_ERROR "libcurl not found. Please install libcurl development package.")
endif()
include_directories(${CURL_INCLUDE_DIRS})

# --- 3. Find Gumbo-parser (For HTML parsing, replacing Selenium's selector/find logic) ---
pkg_search_module(GUMBO REQUIRED gumbo)
if (NOT GUMBO_FOUND)
    message(FATAL_ERROR "gumbo-parser not found. Please install the Gumbo development package.")
endif()
include_directories(${GUMBO_INCLUDE_DIRS})

# --- 4. Find nlohmann/json (For JSON serialization, replacing Python 'json') ---
# Often header-only; we ensure the path to its headers is known.
find_path(NLOHMANN_JSON_INCLUDE_DIR nlohmann/json.hpp
    PATHS
    /usr/include
    /usr/local/include
    # Fallback to a common custom install path
    ${CMAKE_SOURCE_DIR}/third_party/nlohmann_json/include
)
if (NOT NLOHMANN_JSON_INCLUDE_DIR)
    message(FATAL_ERROR "nlohmann/json.hpp not found. You need this for API responses.")
endif()
include_directories(${NLOHMANN_JSON_INCLUDE_DIR})

# --- 5. Find FileSystemUtil (Required by WebClient/DriveSync) ---
# Assuming FileSystemUtil is part of your local source tree
include_directories(${CMAKE_SOURCE_DIR}) 


# --- Define Libraries ---

# Create a static library containing the WebClient and GoogleDriveSync implementation
add_library(WebCoreLib STATIC
    WebClient.cpp
    GoogleDriveSync.cpp
)

# Link the library against all external dependencies
target_link_libraries(WebCoreLib
    PRIVATE
    ${CURL_LIBRARIES}
    ${GUMBO_LIBRARIES}
)

# Handle Windows specific linking needs for sockets/networking
if (WIN32)
    target_link_libraries(WebCoreLib
        PRIVATE
        ws2_32
        crypt32
    )
endif()