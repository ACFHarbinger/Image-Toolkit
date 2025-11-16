cmake_minimum_required(VERSION 3.16)
project(ImageToolkitTests CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# --- 1. FIND GTEST (Required for all tests) ---
find_package(GTest REQUIRED)
include_directories(${GTEST_INCLUDE_DIRS})

# --- 2. FIND ALL OTHER PROJECT DEPENDENCIES ---
find_package(PkgConfig REQUIRED)

# OpenCV (for ImageUtil)
find_package(OpenCV REQUIRED)
include_directories(${OpenCV_INCLUDE_DIRS})

# libcurl (for WebClient, GoogleDriveSync)
find_package(CURL REQUIRED)
include_directories(${CURL_INCLUDE_DIRS})

# Gumbo-parser (for WebClient)
pkg_search_module(GUMBO REQUIRED gumbo)
include_directories(${GUMBO_INCLUDE_DIRS})

# libpqxx (for DatabaseManager)
pkg_search_module(LIBPQXX REQUIRED libpqxx)
include_directories(${LIBPQXX_INCLUDE_DIRS})

# OpenSSL (for VaultManager)
find_package(OpenSSL REQUIRED)
include_directories(${OpenSSL_INCLUDE_DIRS})

# JNI (for VaultManager)
find_package(JNI REQUIRED)
include_directories(${JNI_INCLUDE_DIRS})

# nlohmann/json (for GoogleDriveSync)
find_path(NLOHMANN_JSON_INCLUDE_DIR nlohmann/json.hpp
    PATHS /usr/include /usr/local/include
)
if (NOT NLOHMANN_JSON_INCLUDE_DIR)
    message(FATAL_ERROR "nlohmann/json.hpp not found.")
endif()
include_directories(${NLOHMANN_JSON_INCLUDE_DIR})

# cxxopts (for ArgParser)
find_path(CXXOPTS_INCLUDE_DIR cxxopts.hpp
    PATHS /usr/include /usr/local/include
)
if (NOT CXXOPTS_INCLUDE_DIR)
    message(FATAL_ERROR "cxxopts.hpp not found.")
endif()
include_directories(${CXXOPTS_INCLUDE_DIR})

# --- 3. ADD OUR SOURCE LIBRARIES ---
# Assume all .cpp files are in the parent directory (or add src/ prefix)
# We build them as libraries to link against.
add_library(FileSystemUtil STATIC ../src/core/FileSystemUtil.cpp)
add_library(ImageUtil STATIC ../src/core/ImageUtil.cpp)
add_library(DatabaseManager STATIC ../src/core/DatabaseManager.cpp)
add_library(WallpaperManager STATIC ../src/core/WallpaperManager.cpp)
add_library(VaultManager STATIC ../src/core/VaultManager.cpp)
add_library(WebClient STATIC ../src/web/WebClient.cpp)
add_library(GoogleDriveSync STATIC ../src/web/GoogleDriveSync.cpp)
add_library(ArgParser STATIC ../src/utils/ArgParser.cpp)

# Link dependencies to our libraries
target_link_libraries(ImageUtil PRIVATE FileSystemUtil ${OpenCV_LIBS})
target_link_libraries(DatabaseManager PRIVATE ${LIBPQXX_LIBRARIES})
target_link_libraries(WallpaperManager PRIVATE FileSystemUtil ${OpenCV_LIBS}) # For GNOME span
target_link_libraries(VaultManager PRIVATE FileSystemUtil OpenSSL::Crypto ${JNI_LIBRARIES})
target_link_libraries(WebClient PRIVATE FileSystemUtil ${CURL_LIBRARIES} ${GUMBO_LIBRARIES})
target_link_libraries(GoogleDriveSync PRIVATE FileSystemUtil ${CURL_LIBRARIES})
# ArgParser is self-contained (cxxopts is header-only)

# --- 4. DEFINE TEST EXECUTABLES ---
# We create a separate executable for each test file.

# FileSystemUtil Test
add_executable(FileSystemUtilTest FileSystemUtilTest.cpp)
target_link_libraries(FileSystemUtilTest PRIVATE GTest::gtest_main FileSystemUtil)
add_test(NAME FileSystemUtilTest COMMAND FileSystemUtilTest)

# ArgParser Test
add_executable(ArgParserTest ArgParserTest.cpp)
target_link_libraries(ArgParserTest PRIVATE GTest::gtest_main ArgParser)
add_test(NAME ArgParserTest COMMAND ArgParserTest)

# ImageUtil Test
add_executable(ImageUtilTest ImageUtilTest.cpp)
target_link_libraries(ImageUtilTest PRIVATE GTest::gtest_main ImageUtil FileSystemUtil ${OpenCV_LIBS})
add_test(NAME ImageUtilTest COMMAND ImageUtilTest)

# WebClient Test
add_executable(WebClientTest WebClientTest.cpp)
target_link_libraries(WebClientTest PRIVATE GTest::gtest_main WebClient FileSystemUtil ${CURL_LIBRARIES} ${GUMBO_LIBRARIES})
add_test(NAME WebClientTest COMMAND WebClientTest)

# DatabaseManager Test
add_executable(DatabaseManagerTest DatabaseManagerTest.cpp)
target_link_libraries(DatabaseManagerTest PRIVATE GTest::gtest_main DatabaseManager ${LIBPQXX_LIBRARIES})
add_test(NAME DatabaseManagerTest COMMAND DatabaseManagerTest)

# GoogleDriveSync Test
add_executable(GoogleDriveSyncTest GoogleDriveSyncTest.cpp)
target_link_libraries(GoogleDriveSyncTest PRIVATE GTest::gtest_main GoogleDriveSync FileSystemUtil ${CURL_LIBRARIES})
add_test(NAME GoogleDriveSyncTest COMMAND GoogleDriveSyncTest)

# VaultManager Test
add_executable(VaultManagerTest VaultManagerTest.cpp)
target_link_libraries(VaultManagerTest PRIVATE GTest::gtest_main VaultManager)
add_test(NAME VaultManagerTest COMMAND VaultManagerTest)

# WallpaperManager Test
add_executable(WallpaperManagerTest WallpaperManagerTest.cpp)
target_link_libraries(WallpaperManagerTest PRIVATE GTest::gtest_main WallpaperManager FileSystemUtil)
add_test(NAME WallpaperManagerTest COMMAND WallpaperManagerTest)

# --- 5. ENABLE CTEST TO DISCOVER TESTS ---
include(GoogleTest)