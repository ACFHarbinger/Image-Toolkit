#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/math/graph.hpp
//
// Directed/undirected weighted graph, BFS, DFS, Kruskal MST/max-MST,
// Tarjan SCC, topological sort, and UnionFind.
//
// Header-only — no pybind11 bindings.  Used internally by bundle_adjust.cpp
// (spanning-tree inlier filter) and by the analytics roadmap phases.
//
// Ported from base/src/math/graph.rs.
// ---------------------------------------------------------------------------

#include <algorithm>
#include <cassert>
#include <functional>
#include <numeric>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace base::math {

// ---------------------------------------------------------------------------
// Graph
// ---------------------------------------------------------------------------

/// Directed or undirected weighted graph stored as an adjacency list.
struct Graph {
    struct Edge {
        int dst;
        double weight;
    };

    std::unordered_map<int, std::string>        nodes;   ///< node id → label
    std::unordered_map<int, std::vector<Edge>>  adj;
    bool directed;

    explicit Graph(bool directed = false) : directed(directed) {}

    /// Returns false if node already present.
    bool add_node(int id, const std::string& label = "") {
        if (nodes.count(id)) return false;
        nodes[id] = label;
        adj.emplace(id, std::vector<Edge>{});
        return true;
    }

    void add_edge(int u, int v, double weight = 1.0) {
        adj[u].push_back({v, weight});
        if (!directed) adj[v].push_back({u, weight});
    }

    int node_count() const { return static_cast<int>(nodes.size()); }

    std::vector<int> node_ids() const {
        std::vector<int> ids;
        ids.reserve(nodes.size());
        for (const auto& [id, _] : nodes) ids.push_back(id);
        std::sort(ids.begin(), ids.end());
        return ids;
    }

    const std::vector<Edge>& neighbors(int u) const {
        static const std::vector<Edge> empty{};
        auto it = adj.find(u);
        return it != adj.end() ? it->second : empty;
    }
};

// ---------------------------------------------------------------------------
// BFS / DFS
// ---------------------------------------------------------------------------

inline std::vector<int> bfs(const Graph& g, int start) {
    std::unordered_set<int> visited;
    std::vector<int> queue, order;
    visited.insert(start);
    queue.push_back(start);
    for (int i = 0; i < static_cast<int>(queue.size()); ++i) {
        int u = queue[i];
        order.push_back(u);
        std::vector<int> nbrs;
        for (const auto& e : g.neighbors(u)) nbrs.push_back(e.dst);
        std::sort(nbrs.begin(), nbrs.end());
        for (int v : nbrs) {
            if (visited.insert(v).second) queue.push_back(v);
        }
    }
    return order;
}

inline std::vector<int> dfs(const Graph& g, int start) {
    std::unordered_set<int> visited;
    std::vector<int> stack{start}, order;
    while (!stack.empty()) {
        int u = stack.back(); stack.pop_back();
        if (!visited.insert(u).second) continue;
        order.push_back(u);
        std::vector<int> nbrs;
        for (const auto& e : g.neighbors(u)) nbrs.push_back(e.dst);
        std::sort(nbrs.rbegin(), nbrs.rend());
        for (int v : nbrs) stack.push_back(v);
    }
    return order;
}

// ---------------------------------------------------------------------------
// UnionFind (path compression + union by rank)
// ---------------------------------------------------------------------------

struct UnionFind {
    std::vector<int> parent, rank_;

    explicit UnionFind(int n) : parent(n), rank_(n, 0) {
        std::iota(parent.begin(), parent.end(), 0);
    }

    int find(int x) {
        while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
        return x;
    }

    bool unite(int a, int b) {
        a = find(a); b = find(b);
        if (a == b) return false;
        if (rank_[a] < rank_[b]) std::swap(a, b);
        parent[b] = a;
        if (rank_[a] == rank_[b]) ++rank_[a];
        return true;
    }

    bool connected(int a, int b) { return find(a) == find(b); }
};

// ---------------------------------------------------------------------------
// Kruskal MST (minimum) and max-MST
// ---------------------------------------------------------------------------

struct KruskalEdge { int u, v; double weight; };

/// Returns edges in the minimum spanning tree (Kruskal).
inline std::vector<KruskalEdge> kruskal_mst(int n, std::vector<KruskalEdge> edges) {
    std::sort(edges.begin(), edges.end(),
              [](const KruskalEdge& a, const KruskalEdge& b){ return a.weight < b.weight; });
    UnionFind uf(n);
    std::vector<KruskalEdge> tree;
    for (const auto& e : edges) {
        if (uf.unite(e.u, e.v)) {
            tree.push_back(e);
            if (static_cast<int>(tree.size()) == n - 1) break;
        }
    }
    return tree;
}

/// Returns edges in the maximum spanning tree (highest-weight-first Kruskal).
inline std::vector<KruskalEdge> kruskal_max_mst(int n, std::vector<KruskalEdge> edges) {
    std::sort(edges.begin(), edges.end(),
              [](const KruskalEdge& a, const KruskalEdge& b){ return a.weight > b.weight; });
    UnionFind uf(n);
    std::vector<KruskalEdge> tree;
    for (const auto& e : edges) {
        if (uf.unite(e.u, e.v)) {
            tree.push_back(e);
            if (static_cast<int>(tree.size()) == n - 1) break;
        }
    }
    return tree;
}

// ---------------------------------------------------------------------------
// Tarjan SCC
// ---------------------------------------------------------------------------

struct SCCResult {
    std::vector<std::vector<int>> components; ///< each SCC as sorted node list
    std::vector<int>              comp_id;    ///< node → component index
};

inline SCCResult tarjan_scc(const Graph& g) {
    auto ids = g.node_ids();
    int n = static_cast<int>(ids.size());
    std::unordered_map<int, int> idx_map;
    for (int i = 0; i < n; ++i) idx_map[ids[i]] = i;

    std::vector<int>  disc(n, -1), low(n), comp(n, -1);
    std::vector<bool> on_stack(n, false);
    std::vector<int>  stk;
    int timer = 0, scc_count = 0;
    SCCResult result;
    result.comp_id.resize(n, -1);

    std::function<void(int)> visit = [&](int u) {
        disc[u] = low[u] = timer++;
        stk.push_back(u);
        on_stack[u] = true;
        for (const auto& e : g.neighbors(ids[u])) {
            int v = idx_map.at(e.dst);
            if (disc[v] == -1) { visit(v); low[u] = std::min(low[u], low[v]); }
            else if (on_stack[v]) low[u] = std::min(low[u], disc[v]);
        }
        if (low[u] == disc[u]) {
            std::vector<int> scc;
            while (true) {
                int v = stk.back(); stk.pop_back();
                on_stack[v] = false;
                result.comp_id[v] = scc_count;
                scc.push_back(ids[v]);
                if (v == u) break;
            }
            std::sort(scc.begin(), scc.end());
            result.components.push_back(std::move(scc));
            ++scc_count;
        }
    };

    for (int i = 0; i < n; ++i) if (disc[i] == -1) visit(i);
    return result;
}

// ---------------------------------------------------------------------------
// Topological sort (Kahn's algorithm — throws on cycle)
// ---------------------------------------------------------------------------

inline std::vector<int> topological_sort(const Graph& g) {
    if (!g.directed) throw std::invalid_argument("topological_sort requires a directed graph");
    auto ids = g.node_ids();
    int n = static_cast<int>(ids.size());
    std::unordered_map<int, int> idx;
    for (int i = 0; i < n; ++i) idx[ids[i]] = i;
    std::vector<int> in_degree(n, 0);
    for (int u_idx = 0; u_idx < n; ++u_idx)
        for (const auto& e : g.neighbors(ids[u_idx]))
            ++in_degree[idx.at(e.dst)];
    std::vector<int> queue, order;
    for (int i = 0; i < n; ++i) if (in_degree[i] == 0) queue.push_back(i);
    for (int qi = 0; qi < static_cast<int>(queue.size()); ++qi) {
        int u = queue[qi];
        order.push_back(ids[u]);
        for (const auto& e : g.neighbors(ids[u])) {
            int v = idx.at(e.dst);
            if (--in_degree[v] == 0) queue.push_back(v);
        }
    }
    if (static_cast<int>(order.size()) != n)
        throw std::runtime_error("topological_sort: graph contains a cycle");
    return order;
}

} // namespace base::math
