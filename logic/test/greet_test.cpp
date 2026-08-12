#include "hybrid_image_editor/greet.hpp"
#include "hybrid_image_editor/document.hpp"

#include <gtest/gtest.h>

TEST(Greet, ReturnsExpectedMessage) {
    EXPECT_EQ(hybrid_image_editor::greet("Hybrid-Image-Editor"), "Hello, Hybrid-Image-Editor!");
}

TEST(Greet, HandlesDefaultCase) {
    EXPECT_EQ(hybrid_image_editor::greet("world"), "Hello, world!");
}

TEST(Document, ProvidesVersionedSequenceValueTypes) {
    hybrid_image_editor::Document document;
    document.document_id = "document-1";
    document.sequence.frames.push_back({"source.png", 0});

    EXPECT_EQ(hybrid_image_editor::kDocumentSchemaVersion, 1U);
    EXPECT_EQ(document.sequence.frames.size(), 1U);
}
