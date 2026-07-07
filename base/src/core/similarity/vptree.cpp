// ---------------------------------------------------------------------------
// base/src/core/similarity/vptree.cpp
// Vantage-point tree over Hamming space for perceptual-hash lookups.
// Build: O(N log N), range query: O(log N) expected for small radii.
// ---------------------------------------------------------------------------
#include "core/similarity.hpp"

#include <algorithm>
#include <random>

namespace base::similarity {

VpTree::VpTree(std::vector<BitHash> items) : items_(std::move(items)) {
    if (items_.empty()) return;
    nodes_.reserve(items_.size());
    std::vector<int> idx(items_.size());
    for (size_t i = 0; i < idx.size(); ++i) idx[i] = static_cast<int>(i);
    root_ = build(idx, 0, static_cast<int>(idx.size()));
}

int VpTree::build(std::vector<int>& idx, int lo, int hi) {
    if (lo >= hi) return -1;

    // Deterministic vantage point: first element of the range (the ranges are
    // partitioned by distance, which already decorrelates them adequately).
    Node node;
    node.index = idx[lo];
    int node_pos = static_cast<int>(nodes_.size());
    nodes_.push_back(node);

    if (hi - lo > 1) {
        const BitHash& vp = items_[idx[lo]];
        int mid = lo + 1 + (hi - (lo + 1)) / 2;
        std::nth_element(
            idx.begin() + lo + 1, idx.begin() + mid, idx.begin() + hi,
            [&](int a, int b) {
                return hamming_distance(vp, items_[a]) < hamming_distance(vp, items_[b]);
            });
        uint32_t threshold = hamming_distance(vp, items_[idx[mid]]);
        int left = build(idx, lo + 1, mid);
        int right = build(idx, mid, hi);
        nodes_[node_pos].threshold = threshold;
        nodes_[node_pos].left = left;
        nodes_[node_pos].right = right;
    }
    return node_pos;
}

void VpTree::search(int node, const BitHash& q, uint32_t radius,
                    std::vector<std::pair<size_t, uint32_t>>& out) const {
    if (node < 0) return;
    const Node& n = nodes_[node];
    uint32_t d = hamming_distance(q, items_[n.index]);
    if (d <= radius) out.emplace_back(static_cast<size_t>(n.index), d);

    // Triangle inequality pruning
    if (d + radius >= n.threshold) search(n.right, q, radius, out);
    if (d <= n.threshold + radius) search(n.left, q, radius, out);
}

std::vector<std::pair<size_t, uint32_t>> VpTree::query_radius(const BitHash& query,
                                                              uint32_t radius) const {
    std::vector<std::pair<size_t, uint32_t>> out;
    search(root_, query, radius, out);
    std::sort(out.begin(), out.end(),
              [](const auto& a, const auto& b) { return a.second < b.second; });
    return out;
}

std::vector<std::tuple<size_t, size_t, uint32_t>>
VpTree::pairs_within(uint32_t radius) const {
    std::vector<std::tuple<size_t, size_t, uint32_t>> pairs;
    for (size_t i = 0; i < items_.size(); ++i) {
        auto hits = query_radius(items_[i], radius);
        for (const auto& [j, d] : hits)
            if (j > i) pairs.emplace_back(i, j, d);
    }
    return pairs;
}

}  // namespace base::similarity
