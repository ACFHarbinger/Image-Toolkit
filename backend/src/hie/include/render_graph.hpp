#pragma once

#include <cstddef>
#include <functional>
#include <string>
#include <unordered_map>
#include <vector>

#include "document.hpp"

/// @file render_graph.hpp
/// @brief Directed Acyclic Graph (DAG) render graph evaluator.
///
/// Evaluates a Document's layer stack and modifier node chains in
/// topological order. Caches clean tile regions and skips unmodified
/// sub-graphs for interactive-speed rendering.

namespace hybrid_image_editor {

// ─── Render Tile ─────────────────────────────────────────────────────────────

/// A rectangular dirty region that must be re-evaluated.
struct RenderTile {
    std::uint32_t x      = 0;
    std::uint32_t y      = 0;
    std::uint32_t width  = 0;
    std::uint32_t height = 0;
    bool dirty = true;
};

// ─── Render Node State ────────────────────────────────────────────────────────

/// Evaluation state for a single modifier node in the current render pass.
struct RenderNodeState {
    std::string node_id;
    bool evaluated   = false;
    bool cache_valid = false;
};

// ─── Render Graph ─────────────────────────────────────────────────────────────

/// @brief Topological evaluator for the HIE modifier DAG.
///
/// Usage:
/// @code
///   RenderGraph graph;
///   graph.build(doc);
///   graph.invalidate_layer("layer-id");
///   graph.evaluate(frame_index, on_tile_ready);
/// @endcode
class RenderGraph {
public:
    using TileCallback = std::function<void(const RenderTile&, const std::string& layer_id)>;

    RenderGraph() = default;

    /// Rebuild the evaluation graph from a document snapshot.
    /// Preserves node cache validity where topology is unchanged.
    void build(const Document& doc);

    /// Mark all tiles of a layer dirty (e.g. after a parameter change).
    void invalidate_layer(const std::string& layer_id);

    /// Mark all tiles of a specific modifier node dirty.
    void invalidate_node(const std::string& node_id);

    /// Invalidate the entire graph (e.g. new document opened).
    void invalidate_all();

    /// @brief Evaluate dirty nodes in topological order for `frame_index`.
    ///
    /// Calls `on_tile_ready` for every tile that was re-evaluated.
    /// Skips cache-valid sub-graphs entirely.
    ///
    /// @param frame_index  0-based index into the document's frame sequence.
    /// @param on_tile_ready  Callback invoked per completed render tile.
    void evaluate(std::uint32_t frame_index, const TileCallback& on_tile_ready);

    /// Return topological sort order of modifier node IDs.
    std::vector<std::string> topological_order() const;

    /// True if no dirty tiles remain after the last evaluate() call.
    bool is_clean() const;

private:
    Document                                               doc_snapshot_;
    std::vector<std::string>                               topo_order_;
    std::unordered_map<std::string, RenderNodeState>       node_states_;
    std::vector<RenderTile>                                dirty_tiles_;

    /// Compute topological sort via Kahn's algorithm over modifier_edges.
    void compute_topo_order_();

    /// Propagate dirty flags down the DAG from `start_node`.
    void propagate_dirty_(const std::string& start_node);
};

}  // namespace hybrid_image_editor
