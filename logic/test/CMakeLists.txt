find_package(GTest QUIET)
if(NOT GTest_FOUND)
    include(FetchContent)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.zip
    )
    FetchContent_MakeAvailable(googletest)
endif()

# GTest-based suite (existing greet tests)
add_executable(hybrid_image_editor_tests greet_test.cpp)
target_link_libraries(hybrid_image_editor_tests PRIVATE hybrid_image_editor_logic GTest::gtest_main)
include(GoogleTest)
gtest_discover_tests(hybrid_image_editor_tests)

# Standalone assert-based solver tests (no external deps)
add_executable(hie_solver_tests test_solvers.cpp)
target_link_libraries(hie_solver_tests PRIVATE hybrid_image_editor_logic)
add_test(NAME hie_solver_tests COMMAND hie_solver_tests)
