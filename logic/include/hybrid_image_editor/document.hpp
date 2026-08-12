#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace hybrid_image_editor {

/// Versioned value types shared by future central `base` bindings.
inline constexpr std::uint32_t kDocumentSchemaVersion = 1;

struct Frame {
    std::string source;
    std::uint32_t duration_ms = 0;
};

struct FrameSequence {
    std::vector<Frame> frames;
    double fps = 0.0;
};

struct Modifier {
    std::string id;
    std::string operation;
};

struct Layer {
    std::string id;
    std::string name;
    FrameSequence sequence;
    double opacity = 1.0;
    std::string blend_mode = "normal";
    std::vector<Modifier> modifiers;
};

struct ModifierEdge {
    std::string source;
    std::string target;
};

struct Document {
    std::string document_id;
    FrameSequence sequence;
    std::vector<Layer> layers;
    std::vector<ModifierEdge> edges;
};

}  // namespace hybrid_image_editor
