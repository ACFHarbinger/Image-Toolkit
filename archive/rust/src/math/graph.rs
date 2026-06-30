//! Graph data structures and algorithms for the analytics backbone.
//!
//! Supports Phase 1 (AST/dependency graph construction, semantic layout),
//! Phase 4.2 (causal DAG building), Phase 10 (TDA call-graph analysis), and
//! the spanning-tree / union-find helpers already used by the ASP pipeline
//! (§1.1B, §1.15).

use std::collections::{HashMap, HashSet, VecDeque};

// ── Data model ────────────────────────────────────────────────────────────────

/// A directed or undirected weighted graph represented as an adjacency list.
#[derive(Debug, Clone)]
pub struct Graph {
    /// Mapping from node ID → node metadata label (optional).
    pub nodes: HashMap<usize, String>,
    /// Adjacency list: `adj[u]` = list of `(v, weight)`.
    pub adj: HashMap<usize, Vec<(usize, f64)>>,
    pub directed: bool,
}

impl Graph {
    pub fn new(directed: bool) -> Self {
        Self { nodes: HashMap::new(), adj: HashMap::new(), directed }
    }

    /// Add a node; returns `false` if already present.
    pub fn add_node(&mut self, id: usize, label: &str) -> bool {
        if self.nodes.contains_key(&id) { return false; }
        self.nodes.insert(id, label.to_owned());
        self.adj.entry(id).or_default();
        true
    }

    /// Add an edge `u → v` (and `v → u` for undirected graphs).
    pub fn add_edge(&mut self, u: usize, v: usize, weight: f64) {
        self.adj.entry(u).or_default().push((v, weight));
        if !self.directed {
            self.adj.entry(v).or_default().push((u, weight));
        }
    }

    pub fn node_count(&self) -> usize { self.nodes.len() }
    pub fn edge_count(&self) -> usize { self.adj.values().map(|es| es.len()).sum::<usize>() / if self.directed { 1 } else { 2 } }

    pub fn neighbors(&self, u: usize) -> &[(usize, f64)] {
        self.adj.get(&u).map(|v| v.as_slice()).unwrap_or(&[])
    }

    pub fn node_ids(&self) -> Vec<usize> {
        let mut ids: Vec<usize> = self.nodes.keys().copied().collect();
        ids.sort_unstable();
        ids
    }
}

// ── BFS / DFS ────────────────────────────────────────────────────────────────

/// Breadth-first traversal from `start`. Returns nodes in discovery order.
pub fn bfs(g: &Graph, start: usize) -> Vec<usize> {
    let mut visited = HashSet::new();
    let mut queue = VecDeque::new();
    let mut order = Vec::new();
    visited.insert(start);
    queue.push_back(start);
    while let Some(u) = queue.pop_front() {
        order.push(u);
        let mut nbrs: Vec<usize> = g.neighbors(u).iter().map(|&(v, _)| v).collect();
        nbrs.sort_unstable();
        for v in nbrs {
            if visited.insert(v) { queue.push_back(v); }
        }
    }
    order
}

/// Depth-first traversal from `start`. Returns nodes in discovery order.
pub fn dfs(g: &Graph, start: usize) -> Vec<usize> {
    let mut visited = HashSet::new();
    let mut order = Vec::new();
    dfs_rec(g, start, &mut visited, &mut order);
    order
}

fn dfs_rec(g: &Graph, u: usize, visited: &mut HashSet<usize>, order: &mut Vec<usize>) {
    if !visited.insert(u) { return; }
    order.push(u);
    let mut nbrs: Vec<usize> = g.neighbors(u).iter().map(|&(v, _)| v).collect();
    nbrs.sort_unstable();
    for v in nbrs { dfs_rec(g, v, visited, order); }
}

// ── Topological sort (Kahn's algorithm) ──────────────────────────────────────

/// Topological sort of a directed graph.
///
/// Returns `None` if the graph contains a cycle.  Output is deterministic
/// (ties broken by node ID) — important for reproducible causal DAG ordering.
pub fn topological_sort(g: &Graph) -> Option<Vec<usize>> {
    assert!(g.directed, "topological sort requires a directed graph");
    let mut in_degree: HashMap<usize, usize> = g.nodes.keys().map(|&id| (id, 0)).collect();
    for (_, edges) in &g.adj {
        for &(v, _) in edges {
            *in_degree.entry(v).or_insert(0) += 1;
        }
    }
    // Start queue: all nodes with in-degree 0, sorted for determinism.
    let mut queue: std::collections::BinaryHeap<std::cmp::Reverse<usize>> = in_degree.iter()
        .filter(|(_, &deg)| deg == 0)
        .map(|(&id, _)| std::cmp::Reverse(id))
        .collect();
    let mut order = Vec::new();
    while let Some(std::cmp::Reverse(u)) = queue.pop() {
        order.push(u);
        for &(v, _) in g.neighbors(u) {
            let deg = in_degree.get_mut(&v).unwrap();
            *deg -= 1;
            if *deg == 0 { queue.push(std::cmp::Reverse(v)); }
        }
    }
    if order.len() == g.node_count() { Some(order) } else { None }
}

// ── Connected components (undirected) ────────────────────────────────────────

/// Find all connected components of an **undirected** graph.
///
/// Returns a list of components (each component is a sorted list of node IDs).
pub fn connected_components(g: &Graph) -> Vec<Vec<usize>> {
    let mut visited = HashSet::new();
    let mut components = Vec::new();
    let mut ids = g.node_ids();
    for &start in &ids {
        if !visited.contains(&start) {
            let reachable = bfs(g, start);
            for &id in &reachable { visited.insert(id); }
            let mut comp = reachable;
            comp.sort_unstable();
            components.push(comp);
        }
    }
    ids.clear();
    components
}

// ── Strongly connected components (Tarjan) ───────────────────────────────────

/// Find all strongly connected components using Tarjan's algorithm.
///
/// Returns SCCs in reverse topological order (a property of Tarjan's).
pub fn strongly_connected_components(g: &Graph) -> Vec<Vec<usize>> {
    let mut index_counter = 0usize;
    let mut stack = Vec::new();
    let mut on_stack = HashSet::new();
    let mut indices: HashMap<usize, usize> = HashMap::new();
    let mut lowlinks: HashMap<usize, usize> = HashMap::new();
    let mut sccs: Vec<Vec<usize>> = Vec::new();

    let ids = g.node_ids();
    for &v in &ids {
        if !indices.contains_key(&v) {
            tarjan_scc(g, v, &mut index_counter, &mut stack, &mut on_stack, &mut indices, &mut lowlinks, &mut sccs);
        }
    }
    sccs
}

fn tarjan_scc(
    g: &Graph,
    v: usize,
    index_counter: &mut usize,
    stack: &mut Vec<usize>,
    on_stack: &mut HashSet<usize>,
    indices: &mut HashMap<usize, usize>,
    lowlinks: &mut HashMap<usize, usize>,
    sccs: &mut Vec<Vec<usize>>,
) {
    indices.insert(v, *index_counter);
    lowlinks.insert(v, *index_counter);
    *index_counter += 1;
    stack.push(v);
    on_stack.insert(v);

    let neighbors: Vec<usize> = g.neighbors(v).iter().map(|&(w, _)| w).collect();
    for w in neighbors {
        if !indices.contains_key(&w) {
            tarjan_scc(g, w, index_counter, stack, on_stack, indices, lowlinks, sccs);
            let ll_w = *lowlinks.get(&w).unwrap();
            let ll_v = lowlinks.get_mut(&v).unwrap();
            *ll_v = (*ll_v).min(ll_w);
        } else if on_stack.contains(&w) {
            let idx_w = *indices.get(&w).unwrap();
            let ll_v = lowlinks.get_mut(&v).unwrap();
            *ll_v = (*ll_v).min(idx_w);
        }
    }

    if lowlinks[&v] == indices[&v] {
        let mut scc = Vec::new();
        loop {
            let w = stack.pop().unwrap();
            on_stack.remove(&w);
            scc.push(w);
            if w == v { break; }
        }
        scc.sort_unstable();
        sccs.push(scc);
    }
}

// ── Union-Find ────────────────────────────────────────────────────────────────

/// Path-compressed, rank-unioned Union-Find over integer IDs in `[0, n)`.
pub struct UnionFind {
    parent: Vec<usize>,
    rank: Vec<usize>,
}

impl UnionFind {
    pub fn new(n: usize) -> Self {
        Self { parent: (0..n).collect(), rank: vec![0; n] }
    }

    pub fn find(&mut self, x: usize) -> usize {
        if self.parent[x] != x {
            self.parent[x] = self.find(self.parent[x]);
        }
        self.parent[x]
    }

    /// Returns `true` if `x` and `y` were in different sets (i.e., a union happened).
    pub fn union(&mut self, x: usize, y: usize) -> bool {
        let rx = self.find(x);
        let ry = self.find(y);
        if rx == ry { return false; }
        if self.rank[rx] < self.rank[ry] {
            self.parent[rx] = ry;
        } else if self.rank[rx] > self.rank[ry] {
            self.parent[ry] = rx;
        } else {
            self.parent[ry] = rx;
            self.rank[rx] += 1;
        }
        true
    }

    pub fn connected(&mut self, x: usize, y: usize) -> bool {
        self.find(x) == self.find(y)
    }
}

// ── Minimum spanning tree (Kruskal) ──────────────────────────────────────────

/// Minimum spanning tree via Kruskal's algorithm.
///
/// Input: `n` nodes (IDs 0..n-1), list of `(u, v, weight)` edges.
/// Returns the MST edges (at most n-1).
pub fn kruskal_mst(n: usize, edges: &[(usize, usize, f64)]) -> Vec<(usize, usize, f64)> {
    let mut sorted: Vec<_> = edges.to_vec();
    sorted.sort_by(|a, b| a.2.partial_cmp(&b.2).unwrap());
    let mut uf = UnionFind::new(n);
    let mut mst = Vec::new();
    for (u, v, w) in sorted {
        if uf.union(u, v) { mst.push((u, v, w)); }
        if mst.len() == n - 1 { break; }
    }
    mst
}

/// Maximum spanning tree (highest-weight edges first) — used by §1.1B spanning
/// tree consensus pre-filter in the ASP pipeline.
pub fn kruskal_max_mst(n: usize, edges: &[(usize, usize, f64)]) -> Vec<(usize, usize, f64)> {
    let mut sorted: Vec<_> = edges.to_vec();
    sorted.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap());
    let mut uf = UnionFind::new(n);
    let mut mst = Vec::new();
    for (u, v, w) in sorted {
        if uf.union(u, v) { mst.push((u, v, w)); }
        if mst.len() == n - 1 { break; }
    }
    mst
}

// ── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn small_dag() -> Graph {
        let mut g = Graph::new(true);
        for i in 0..5 { g.add_node(i, &format!("n{i}")); }
        // 0→1, 0→2, 1→3, 2→3, 3→4
        g.add_edge(0, 1, 1.0); g.add_edge(0, 2, 1.0);
        g.add_edge(1, 3, 1.0); g.add_edge(2, 3, 1.0);
        g.add_edge(3, 4, 1.0);
        g
    }

    #[test]
    fn test_bfs_order() {
        let g = small_dag();
        let order = bfs(&g, 0);
        assert_eq!(order[0], 0);
        assert!(order.contains(&4));
    }

    #[test]
    fn test_topological_sort_dag() {
        let g = small_dag();
        let order = topological_sort(&g).unwrap();
        assert_eq!(order.len(), 5);
        // 0 must come before 1, 2 must come before 3, 3 before 4.
        let pos: HashMap<usize, usize> = order.iter().enumerate().map(|(i, &v)| (v, i)).collect();
        assert!(pos[&0] < pos[&1]);
        assert!(pos[&2] < pos[&3]);
        assert!(pos[&3] < pos[&4]);
    }

    #[test]
    fn test_topological_sort_cycle_returns_none() {
        let mut g = Graph::new(true);
        for i in 0..3 { g.add_node(i, ""); }
        g.add_edge(0, 1, 1.0); g.add_edge(1, 2, 1.0); g.add_edge(2, 0, 1.0);
        assert!(topological_sort(&g).is_none());
    }

    #[test]
    fn test_connected_components() {
        let mut g = Graph::new(false);
        for i in 0..6 { g.add_node(i, ""); }
        g.add_edge(0, 1, 1.0); g.add_edge(1, 2, 1.0);
        g.add_edge(3, 4, 1.0);
        // node 5 is isolated
        let comps = connected_components(&g);
        assert_eq!(comps.len(), 3);
    }

    #[test]
    fn test_scc_simple() {
        let mut g = Graph::new(true);
        for i in 0..3 { g.add_node(i, ""); }
        g.add_edge(0, 1, 1.0); g.add_edge(1, 2, 1.0); g.add_edge(2, 0, 1.0);
        let sccs = strongly_connected_components(&g);
        assert_eq!(sccs.len(), 1);
        assert_eq!(sccs[0].len(), 3);
    }

    #[test]
    fn test_union_find() {
        let mut uf = UnionFind::new(5);
        assert!(!uf.connected(0, 4));
        uf.union(0, 1); uf.union(1, 2); uf.union(3, 4);
        assert!(uf.connected(0, 2));
        assert!(!uf.connected(0, 3));
    }

    #[test]
    fn test_kruskal_mst() {
        let edges = vec![(0,1,1.0),(0,2,4.0),(1,2,2.0),(1,3,5.0),(2,3,3.0)];
        let mst = kruskal_mst(4, &edges);
        assert_eq!(mst.len(), 3);
        let total: f64 = mst.iter().map(|e| e.2).sum();
        assert!((total - 6.0).abs() < 1e-10); // 1+2+3 = 6
    }

    #[test]
    fn test_kruskal_max_mst() {
        let edges = vec![(0,1,1.0),(0,2,4.0),(1,2,2.0),(1,3,5.0),(2,3,3.0)];
        let mst = kruskal_max_mst(4, &edges);
        assert_eq!(mst.len(), 3);
        let total: f64 = mst.iter().map(|e| e.2).sum();
        assert!((total - 12.0).abs() < 1e-10); // 5+4+3 = 12
    }
}
