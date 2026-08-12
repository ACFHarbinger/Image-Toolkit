/// @file render_graph.cpp
/// @brief Topological DAG render graph evaluator implementation.

#include "render_graph.hpp"

#include <algorithm>
#include <queue>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>

namespace hybrid_image_editor {

// ─── build ────────────────────────────────────────────────────────────────────

void RenderGraph::build(const Document& doc) {
    doc_snapshot_ = doc;
    node_states_.clear();

    // Register every modifier node from every layer
    for (const auto& layer : doc.layers) {
        for (const auto& node : layer.modifiers) {
            if (node_states_.find(node.id) == node_states_.end()) {
                RenderNodeState state;
                state.node_id     = node.id;
                state.evaluated   = false;
                state.cache_valid = false;
                node_states_[node.id] = state;
            }
        }
    }

    compute_topo_order_();

    // Seed dirty tiles covering the full canvas (if any frames exist)
    dirty_tiles_.clear();
    if (!doc.frame_sequence.frames.empty()) {
        RenderTile full;
        full.x = full.y = 0;
        full.width  = 0xFFFF;  // sentinel: "whole canvas"
        full.height = 0xFFFF;
        full.dirty  = true;
        dirty_tiles_.push_back(full);
    }
}

// ─── Topological sort (Kahn's algorithm) ─────────────────────────────────────

void RenderGraph::compute_topo_order_() {
    topo_order_.clear();

    // Build adjacency and in-degree tables from modifier_edges
    std::unordered_map<std::string, std::vector<std::string>> adj;
    std::unordered_map<std::string, int> in_degree;

    for (const auto& [id, _] : node_states_) {
        in_degree[id] = 0;
        adj[id];  // ensure key exists
    }

    for (const auto& edge : doc_snapshot_.modifier_edges) {
        adj[edge.source].push_back(edge.target);
        in_degree[edge.target]++;
    }

    // Kahn's BFS topological sort
    std::queue<std::string> q;
    for (const auto& [id, deg] : in_degree) {
        if (deg == 0) {
            q.push(id);
        }
    }

    while (!q.empty()) {
        auto node = q.front();
        q.pop();
        topo_order_.push_back(node);

        for (const auto& neighbour : adj[node]) {
            if (--in_degree[neighbour] == 0) {
                q.push(neighbour);
            }
        }
    }

    // Cycle detection
    if (topo_order_.size() != node_states_.size()) {
        // Cycle in modifier DAG: fall back to registration order
        topo_order_.clear();
        for (const auto& [id, _] : node_states_) {
            topo_order_.push_back(id);
        }
    }
}

// ─── Invalidation ─────────────────────────────────────────────────────────────

void RenderGraph::invalidate_layer(const std::string& layer_id) {
    for (const auto& layer : doc_snapshot_.layers) {
        if (layer.id == layer_id) {
            for (const auto& node : layer.modifiers) {
                if (node_states_.count(node.id)) {
                    node_states_[node.id].cache_valid = false;
                    node_states_[node.id].evaluated   = false;
                    propagate_dirty_(node.id);
                }
            }
        }
    }
}

void RenderGraph::invalidate_node(const std::string& node_id) {
    if (node_states_.count(node_id)) {
        node_states_[node_id].cache_valid = false;
        node_states_[node_id].evaluated   = false;
        propagate_dirty_(node_id);
    }
}

void RenderGraph::invalidate_all() {
    for (auto& [id, state] : node_states_) {
        state.cache_valid = false;
        state.evaluated   = false;
    }
    for (auto& tile : dirty_tiles_) {
        tile.dirty = true;
    }
}

void RenderGraph::propagate_dirty_(const std::string& start_node) {
    // BFS downstream dirty propagation
    std::queue<std::string> q;
    q.push(start_node);

    while (!q.empty()) {
        auto node = q.front();
        q.pop();

        for (const auto& edge : doc_snapshot_.modifier_edges) {
            if (edge.source == node) {
                auto it = node_states_.find(edge.target);
                if (it != node_states_.end() && it->second.cache_valid) {
                    it->second.cache_valid = false;
                    it->second.evaluated   = false;
                    q.push(edge.target);
                }
            }
        }
    }
}

// ─── evaluate ─────────────────────────────────────────────────────────────────

void RenderGraph::evaluate(std::uint32_t /*frame_index*/,
                           const TileCallback& on_tile_ready) {
    // Evaluate nodes in topological order; skip cache-valid nodes
    for (const auto& node_id : topo_order_) {
        auto it = node_states_.find(node_id);
        if (it == node_states_.end()) continue;

        auto& state = it->second;
        if (state.cache_valid) continue;

        // TODO: Dispatch to per-node-type pixel processor
        //       (matting, colour harmonisation, PSO-tuned filter, …)
        //       For now mark as evaluated and emit the dirty tile.
        state.evaluated   = true;
        state.cache_valid = true;

        for (auto& tile : dirty_tiles_) {
            if (tile.dirty) {
                on_tile_ready(tile, node_id);
            }
        }
    }

    // Clear dirty tiles after a full evaluation pass
    for (auto& tile : dirty_tiles_) {
        tile.dirty = false;
    }
}

// ─── Accessors ───────────────────────────────────────────────────────────────

std::vector<std::string> RenderGraph::topological_order() const {
    return topo_order_;
}

bool RenderGraph::is_clean() const {
    return std::all_of(dirty_tiles_.begin(), dirty_tiles_.end(),
                       [](const RenderTile& t) { return !t.dirty; });
}

}  // namespace hybrid_image_editor
