#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <vector>

/// @file document.hpp
/// @brief Core multi-modal document data model for the Hybrid Image Editor.
///
/// Versioned value types shared by the C++ logic core and the Python
/// middleware via the central Image-Toolkit `base` pybind11 bindings.
/// A still image is represented as a one-frame FrameSequence (length == 1).

namespace hybrid_image_editor {

/// Schema version — bump on any breaking struct change.
inline constexpr std::uint32_t kDocumentSchemaVersion = 2;

// ─── Media Asset ─────────────────────────────────────────────────────────────

/// A raw source asset (image file, video clip) referenced by frames.
struct MediaAsset {
    std::string id;           ///< UUID or stable hash
    std::string path;         ///< Absolute filesystem path
    std::string format;       ///< MIME type or extension: "image/jpeg", "video/mp4"
    std::uint32_t width  = 0; ///< Pixel width
    std::uint32_t height = 0; ///< Pixel height
    std::uint32_t frame_count = 1; ///< 1 for still images; N for video clips
};

// ─── Frame ───────────────────────────────────────────────────────────────────

/// A single temporal frame referencing a source asset.
struct Frame {
    std::uint32_t index       = 0; ///< 0-based position in the sequence
    std::string   asset_id;        ///< ID of the MediaAsset this frame draws from
    double        timestamp_ms = 0.0; ///< Playback timestamp in milliseconds
};

/// An ordered sequence of frames; length == 1 for a static image document.
struct FrameSequence {
    std::vector<Frame> frames;
    double fps = 0.0; ///< 0.0 for still-image documents
};

// ─── Modifier / Render Node ───────────────────────────────────────────────────

/// A non-destructive processing node attached to a layer.
/// @note `params` maps parameter names to serialised string values.
struct ModifierNode {
    std::string id;                          ///< UUID
    std::string type;                        ///< "matting", "superres", "pso_tune", …
    std::map<std::string, std::string> params; ///< Key→value parameter bag
    bool enabled = true;
};

/// Deprecated alias kept for backward compatibility.
using Modifier = ModifierNode;

/// Directed edge in the modifier DAG: source node feeds into target node.
struct ModifierEdge {
    std::string source; ///< Source ModifierNode::id
    std::string target; ///< Target ModifierNode::id
};

// ─── Layer ───────────────────────────────────────────────────────────────────

/// A compositing layer in the document layer stack.
struct Layer {
    std::string id;
    std::string name;
    FrameSequence sequence;                ///< Per-layer frame overrides (empty → use document sequence)
    double opacity = 1.0;                  ///< [0.0, 1.0]
    std::string blend_mode = "normal";     ///< "normal", "multiply", "screen", "overlay", …
    bool visible = true;
    std::vector<ModifierNode> modifiers;   ///< Ordered modifier chain
};

// ─── Document ────────────────────────────────────────────────────────────────

/// Root document object: a layer stack over a shared frame sequence.
struct Document {
    std::string     document_id;
    std::uint32_t   schema_version = kDocumentSchemaVersion;
    FrameSequence   frame_sequence;            ///< Shared timeline; length == 1 for still images
    std::vector<Layer> layers;                 ///< Bottom-to-top composite order
    std::vector<ModifierEdge> modifier_edges;  ///< Inter-node DAG edges
    std::uint32_t active_frame_index = 0;      ///< Currently displayed frame
};

}  // namespace hybrid_image_editor
