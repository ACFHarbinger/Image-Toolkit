cmake_minimum_required(VERSION 3.16)

project(Utils LANGUAGES CXX)

# Find JSON library
find_package(nlohmann_json REQUIRED)

# Set path to Core modules
set(CORE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../core)

# Define Executable
# We include wallpaper_manager.cpp directly here to link its logic
add_executable(Utils
    SlideshowDaemon.cpp
    SlideshowDaemon.hpp
    ${CORE_DIR}/WallpaperManager.cpp
)

# Include headers from core
target_include_directories(Utils PRIVATE ${CORE_DIR})

# Platform Specific Dependencies
if(UNIX AND NOT APPLE)
    # Linux: Requires X11/XRandR for monitor detection
    find_package(X11 REQUIRED)
    target_link_libraries(Utils PRIVATE ${X11_LIBRARIES} ${X11_Xrandr_LIB})
elseif(WIN32)
    # Windows: Requires User32 for EnumDisplayMonitors, Ole32 for COM
    target_link_libraries(Utils PRIVATE User32 Ole32 OleAut32)
endif()

# Common Links
target_link_libraries(Utils PRIVATE nlohmann_json::nlohmann_json)