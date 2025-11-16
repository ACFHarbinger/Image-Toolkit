cmake_minimum_required(VERSION 3.16)
project(CoreCppLib CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# --- Find Dependencies ---

# 1. Find PkgConfig to help find other libraries
find_package(PkgConfig REQUIRED)

# 2. Find OpenCV
# This will use PkgConfig to find OpenCV
find_package(OpenCV REQUIRED)
if (NOT OpenCV_FOUND)
    message(FATAL_ERROR "OpenCV not found.")
endif()
include_directories(${OpenCV_INCLUDE_DIRS})

# 3. Find libpqxx (for PostgreSQL)
# This uses PkgConfig to find libpq (C lib) and libpqxx (C++ wrapper)
pkg_search_module(PQXX REQUIRED libpqxx)
if (NOT PQXX_FOUND)
    message(FATAL_ERROR "libpqxx not found.")
endif()
include_directories(${PQXX_INCLUDE_DIRS})

# 4. Find OpenSSL (for crypto)
find_package(OpenSSL REQUIRED)
if (NOT OpenSSL_FOUND)
    message(FATAL_ERROR "OpenSSL not found.")
endif()
include_directories(${OpenSSL_INCLUDE_DIRS})

# 5. Find JNI (Java Native Interface)
# This is part of the JDK
find_package(JNI REQUIRED)
if (NOT JNI_FOUND)
    message(FATAL_ERROR "JNI (Java Development Kit) not found.")
endif()
include_directories(${JNI_INCLUDE_DIRS})


# --- Define Libraries ---

# We'll create a static library for our core logic
add_library(CoreLib STATIC
    FileSystemUtil.cpp
    ImageUtil.cpp
    DatabaseManager.cpp
    WallpaperManager.cpp
    VaultManager.cpp
)

# Link our library against all its dependencies
target_link_libraries(CoreLib
    PRIVATE
    ${OpenCV_LIBS}
    ${PQXX_LIBRARIES}
    ${OpenSSL_LIBRARIES}
    ${JNI_LIBRARIES}
)

# On Windows, we also need system libraries
if (WIN32)
    target_link_libraries(CoreLib
        PRIVATE
        user32
        advapi32
        ws2_32  # Required by libpq
        secur32 # Required by libpq
    )
endif()

# --- Example Executable ---
# This shows how an application (like your GUI) would use the library
# add_executable(MyApp main.cpp)
# target_link_libraries(MyApp PRIVATE CoreLib)