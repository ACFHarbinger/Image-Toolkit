cmake_minimum_required(VERSION 3.16)
project(ImageToolkit_Parent CXX)

# Set the required C++ standard for the entire project
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Enable CTest integration for test discovery
enable_testing()

# --- 1. FIND TOP-LEVEL DEPENDENCIES (Needed by multiple subdirectories) ---
# Finding these at the root ensures consistent versions across sub-projects.

# --- JNI Fix: Use environment variables as search hints ---
# Check for manually set environment variable AWT_LIBRARY (fix for missing AWT on some systems)
if (NOT AWT_LIBRARY)
    if (DEFINED ENV{AWT_LIBRARY})
        set(AWT_LIBRARY $ENV{AWT_LIBRARY})
    endif()
endif()

# Check for manually set environment variable JAVA_HOME
if (NOT JAVA_HOME)
    if (DEFINED ENV{JAVA_HOME})
        set(JAVA_HOME $ENV{JAVA_HOME})
    endif()
endif()

# Provide AWT_LIBRARY hint to CMake's FindJNI module
if (AWT_LIBRARY)
    set(JAVA_AWT_LIBRARY ${AWT_LIBRARY} CACHE FILEPATH "Path to the AWT library for JNI.")
endif()
# --- End JNI Fix 
# ---

# --- HARDCODED JNI PATHS FOR OPENJDK 21 (Resolves all missing components) ---
# These paths are fixed based on your successful command-line configuration.
set(JAVA_HOME                       "/usr/lib/jvm/java-21-openjdk-amd64" CACHE PATH "JDK base path")
set(JAVA_INCLUDE_PATH               "/usr/lib/jvm/java-21-openjdk-amd64/include" CACHE PATH "JNI headers")
set(JAVA_INCLUDE_PATH2              "/usr/lib/jvm/java-21-openjdk-amd64/include/linux" CACHE PATH "OS-specific JNI headers")
set(JAVA_AWT_LIBRARY                "/usr/lib/jvm/java-21-openjdk-amd64/lib/libawt.so" CACHE FILEPATH "AWT library")
set(JAVA_JVM_LIBRARY                "/usr/lib/jvm/java-21-openjdk-amd64/lib/server/libjvm.so" CACHE FILEPATH "JVM server library")
set(JAVA_JAWT_LIBRARY               "/usr/lib/jvm/java-21-openjdk-amd64/lib/libjawt.so" CACHE FILEPATH "JAWT library")
set(JAVA_JAVA_LIBRARY               "/usr/lib/jvm/java-21-openjdk-amd64/lib/libjava.so" CACHE FILEPATH "libjava library")
set(JAVA_AWT_INCLUDE_PATH           "/usr/lib/jvm/java-21-openjdk-amd64/include" CACHE PATH "AWT include path")
# --- END HARDCODED JNI PATHS ---


find_package(GTest REQUIRED)
find_package(PkgConfig REQUIRED)
find_package(OpenCV REQUIRED)
find_package(CURL REQUIRED)
find_package(OpenSSL REQUIRED)

# The FindJNI module will now use the hardcoded variables above.
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