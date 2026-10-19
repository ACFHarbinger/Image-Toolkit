cmake_minimum_required(VERSION 3.18)
project(argon2 C)

add_library(argon2 STATIC
    src/argon2.c
    src/core.c
    src/encoding.c
    src/opt.c
    src/thread.c
    src/blake2/blake2b.c
)
set_target_properties(argon2 PROPERTIES POSITION_INDEPENDENT_CODE ON)


target_include_directories(argon2 PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Optimization flags for argon2
if(CMAKE_COMPILER_IS_GNUCC OR CMAKE_C_COMPILER_ID MATCHES "Clang")
    target_compile_options(argon2 PRIVATE -O3 -pthread)
endif()
