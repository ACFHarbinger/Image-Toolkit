find_package(GTest QUIET)
if(NOT GTest_FOUND)
    include(FetchContent)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.zip
    )
    FetchContent_MakeAvailable(googletest)
endif()

add_executable(hybrid_image_editor_tests greet_test.cpp)
target_link_libraries(hybrid_image_editor_tests PRIVATE hybrid_image_editor_logic GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(hybrid_image_editor_tests)
