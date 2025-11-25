cmake_minimum_required(VERSION 3.16)

project(CppCloudSync LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt6 REQUIRED COMPONENTS Core Network NetworkAuth)

add_executable(CppCloudSync
    main.cpp
    abstract_sync.h
    one_drive_sync.cpp
    one_drive_sync.h
    dropbox_sync.cpp
    dropbox_sync.h
    google_drive_sync.cpp
    google_drive_sync.h
)

target_link_libraries(CppCloudSync PRIVATE
    Qt6::Core
    Qt6::Network
    Qt6::NetworkAuth
)