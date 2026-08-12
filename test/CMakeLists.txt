find_package(GTest QUIET)
if(NOT GTest_FOUND)
    include(FetchContent)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.zip
    )
    FetchContent_MakeAvailable(googletest)
endif()

add_executable(single_module_template_tests greet_test.cpp)
target_link_libraries(single_module_template_tests PRIVATE single_module_template_lib GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(single_module_template_tests)
