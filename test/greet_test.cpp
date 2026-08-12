#include "single_module_template/greet.hpp"

#include <gtest/gtest.h>

TEST(Greet, ReturnsExpectedMessage) {
    EXPECT_EQ(single_module_template::greet("Single-Module-Template"), "Hello, Single-Module-Template!");
}

TEST(Greet, HandlesDefaultCase) {
    EXPECT_EQ(single_module_template::greet("world"), "Hello, world!");
}
