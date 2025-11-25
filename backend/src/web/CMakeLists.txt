cmake_minimum_required(VERSION 3.16)

project(CppCloudSync LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt6 REQUIRED COMPONENTS Core Network NetworkAuth)

add_executable(CppCloudSync
    main.cpp
    # Cloud Synchronization
    AbstractCloudSync.hpp
    OneDriveSync.cpp
    OneDriveSync.hpp
    DropboxSync.cpp
    DropboxSync.hpp
    GoogleDriveSync.cpp
    GoogleDriveSync.hpp
    # Web Browser
    WebDriverClient.hpp
    WebRequests.cpp
    WebRequests.hpp
    ImageCrawler.cpp
    ImageCrawler.hpp
)

target_link_libraries(CppCloudSync PRIVATE
    Qt6::Core
    Qt6::Network
    Qt6::NetworkAuth
)