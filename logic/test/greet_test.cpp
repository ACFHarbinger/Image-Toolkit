#include "hybrid_image_editor/greet.hpp"

#include <gtest/gtest.h>

TEST(Greet, ReturnsExpectedMessage) {
    EXPECT_EQ(hybrid_image_editor::greet("Hybrid-Image-Editor"), "Hello, Hybrid-Image-Editor!");
}

TEST(Greet, HandlesDefaultCase) {
    EXPECT_EQ(hybrid_image_editor::greet("world"), "Hello, world!");
}
