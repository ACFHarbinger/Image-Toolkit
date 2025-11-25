cmake_minimum_required(VERSION 3.16)

project(ImageToolsCpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# --- Find Dependencies ---

# 1. OpenCV: Required for image processing (ImageMerger, ImageFinder)
find_package(OpenCV REQUIRED)

# 2. OpenSSL: Required for cryptographic hashing (VaultManager)
find_package(OpenSSL REQUIRED)

# 3. JNI: Required for Java/Kotlin Interop (VaultManager)
find_package(JNI REQUIRED)

# 4. JSON: Required for Vault data serialization
# Note: Ensure nlohmann-json-dev is installed
find_package(nlohmann_json REQUIRED)

# 5. libpqxx: Required for PostgreSQL Database access (ImageDatabase)
find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBPQXX REQUIRED IMPORTED_TARGET libpqxx)

# 6. PostgreSQL Client Library
find_package(PostgreSQL REQUIRED)

# --- Define Executable ---

add_executable(ImageTool 
    main.cpp
    # File System
    FileSystemTool.cpp
    FileSystemTool.hpp
    # Image Tools
    ImageFinder.cpp
    ImageFinder.hpp
    ImageFormatConverter.cpp
    ImageFormatConverter.hpp
    ImageMerger.cpp
    ImageMerger.hpp
    # Vault Manager (JNI)
    VaultManager.cpp
    VaultManager.hpp
    # Image Database (libpqxx)
    ImageDatabase.cpp
    ImageDatabase.hpp
    # Wallpaper Manager
    WallpaperManager.cpp
    WallpaperManager.hpp
)

# --- Include Directories ---

target_include_directories(ImageTool PRIVATE
    ${JNI_INCLUDE_DIRS}
    ${PostgreSQL_INCLUDE_DIRS}
    # libpqxx include dirs are handled by the PkgConfig imported target usually, 
    # but explicitly adding JNI and Postgres ensures system headers are found.
)

# --- Link Libraries ---

target_link_libraries(ImageTool PRIVATE 
    ${OpenCV_LIBS} 
    OpenSSL::Crypto
    ${JNI_LIBRARIES}
    nlohmann_json::nlohmann_json
    PkgConfig::LIBPQXX
    PostgreSQL::pq
)