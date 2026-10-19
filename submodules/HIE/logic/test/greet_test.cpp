#include "greet.hpp"
#include "document.hpp"

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

    hybrid_image_editor::Frame frame;
    frame.index = 0;
    frame.asset_id = "source.png";
    frame.timestamp_ms = 0.0;
    document.frame_sequence.frames.push_back(frame);

    EXPECT_GE(hybrid_image_editor::kDocumentSchemaVersion, 2U);
    EXPECT_EQ(document.frame_sequence.frames.size(), 1U);
    EXPECT_EQ(document.frame_sequence.frames[0].asset_id, "source.png");
}

TEST(Document, LayerHasModifiersAndBlendMode) {
    hybrid_image_editor::Layer layer;
    layer.id         = "layer-0";
    layer.name       = "Background";
    layer.opacity    = 0.8;
    layer.blend_mode = "multiply";
    layer.visible    = true;

    hybrid_image_editor::ModifierNode node;
    node.id      = "node-0";
    node.type    = "superres";
    node.enabled = true;
    layer.modifiers.push_back(node);

    EXPECT_EQ(layer.modifiers.size(), 1U);
    EXPECT_EQ(layer.blend_mode, "multiply");
}
