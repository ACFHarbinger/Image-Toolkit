/** Graph data structures and Fruchterman-Reingold force-directed layout for
 *  the analytics dependency graph visualisation (Phase 1, Phase 4.2). */

import { Vec2, add2, sub2, scale2, len2 } from './linalg';

export interface GraphNode {
  id: string;
  label?: string;
  /** Initial / current 2-D position for layout. */
  pos?: Vec2;
  /** Arbitrary metadata (file path, module name, …). */
  meta?: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  weight?: number;
}

export class Graph {
  readonly nodes = new Map<string, GraphNode>();
  readonly adj = new Map<string, GraphEdge[]>();
  readonly directed: boolean;

  constructor(directed = true) {
    this.directed = directed;
  }

  addNode(node: GraphNode): void {
    this.nodes.set(node.id, node);
    if (!this.adj.has(node.id)) this.adj.set(node.id, []);
  }

  addEdge(edge: GraphEdge): void {
    const list = this.adj.get(edge.source) ?? [];
    list.push(edge);
    this.adj.set(edge.source, list);
    if (!this.directed) {
      const rev = this.adj.get(edge.target) ?? [];
      rev.push({ source: edge.target, target: edge.source, weight: edge.weight });
      this.adj.set(edge.target, rev);
    }
  }

  neighbors(id: string): GraphEdge[] {
    return this.adj.get(id) ?? [];
  }

  nodeIds(): string[] {
    return Array.from(this.nodes.keys()).sort();
  }

  get nodeCount(): number { return this.nodes.size; }
}

// ── BFS / topological sort ───────────────────────────────────────────────────

export function bfs(g: Graph, start: string): string[] {
  const visited = new Set<string>();
  const queue: string[] = [start];
  const order: string[] = [];
  visited.add(start);
  while (queue.length > 0) {
    const u = queue.shift()!;
    order.push(u);
    const nbrs = g.neighbors(u).map(e => e.target).sort();
    for (const v of nbrs) {
      if (!visited.has(v)) {
        visited.add(v);
        queue.push(v);
      }
    }
  }
  return order;
}

/** Kahn's topological sort. Returns `null` if the graph contains a cycle. */
export function topologicalSort(g: Graph): string[] | null {
  const inDeg = new Map<string, number>();
  for (const id of g.nodeIds()) inDeg.set(id, 0);
  for (const edges of g.adj.values()) {
    for (const e of edges) inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1);
  }

  const queue = g.nodeIds().filter(id => (inDeg.get(id) ?? 0) === 0);
  const order: string[] = [];
  while (queue.length > 0) {
    queue.sort();
    const u = queue.shift()!;
    order.push(u);
    for (const e of g.neighbors(u)) {
      const deg = (inDeg.get(e.target) ?? 1) - 1;
      inDeg.set(e.target, deg);
      if (deg === 0) queue.push(e.target);
    }
  }
  return order.length === g.nodeCount ? order : null;
}

// ── Fruchterman-Reingold force-directed layout ────────────────────────────────

export interface FROptions {
  /** Canvas width. */
  width?: number;
  /** Canvas height. */
  height?: number;
  iterations?: number;
  /** Ideal spring length; defaults to auto-computed. */
  k?: number;
}

export interface LayoutNode {
  id: string;
  x: number;
  y: number;
}

/**
 * Fruchterman-Reingold force-directed layout.
 *
 * Returns `{id, x, y}` for every node in the graph.  Coordinates are in
 * `[0, width] × [0, height]`.  Used for the Phase 1 AST dependency graph.
 */
export function fruchtermanReingold(
  g: Graph,
  opts: FROptions = {},
): LayoutNode[] {
  const W = opts.width ?? 800;
  const H = opts.height ?? 600;
  const iters = opts.iterations ?? 300;
  const area = W * H;
  const n = g.nodeCount;
  const k = opts.k ?? Math.sqrt(area / Math.max(n, 1));

  // Seeded initial positions on a circle for determinism.
  const ids = g.nodeIds();
  const pos = new Map<string, Vec2>(
    ids.map((id, i) => [
      id,
      [
        W / 2 + (W / 3) * Math.cos((2 * Math.PI * i) / ids.length),
        H / 2 + (H / 3) * Math.sin((2 * Math.PI * i) / ids.length),
      ],
    ]),
  );

  const fa = (d: number): number => (d * d) / k;
  const fr = (d: number): number => (k * k) / d;

  let temp = W / 10;
  const cool = temp / (iters + 1);

  for (let iter = 0; iter < iters; iter++) {
    const disp = new Map<string, Vec2>(ids.map(id => [id, [0, 0]]));

    // Repulsive forces between every pair.
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const u = ids[i];
        const v = ids[j];
        const delta = sub2(pos.get(u)!, pos.get(v)!);
        const dist = Math.max(len2(delta), 0.01);
        const force = fr(dist) / dist;
        const fvec = scale2(delta, force);
        disp.set(u, add2(disp.get(u)!, fvec));
        disp.set(v, [disp.get(v)![0] - fvec[0], disp.get(v)![1] - fvec[1]]);
      }
    }

    // Attractive forces along edges.
    for (const edges of g.adj.values()) {
      for (const e of edges) {
        if (!g.directed && e.source > e.target) continue; // undirected: process once
        const pu = pos.get(e.source);
        const pv = pos.get(e.target);
        if (!pu || !pv) continue;
        const delta = sub2(pu, pv);
        const dist = Math.max(len2(delta), 0.01);
        const force = fa(dist) / dist;
        const fvec = scale2(delta, force);
        disp.set(e.source, [disp.get(e.source)![0] - fvec[0], disp.get(e.source)![1] - fvec[1]]);
        disp.set(e.target, add2(disp.get(e.target)!, fvec));
      }
    }

    // Limit displacement and cool.
    for (const id of ids) {
      const d = disp.get(id)!;
      const dl = Math.max(len2(d), 0.01);
      const limited = scale2(d, Math.min(dl, temp) / dl);
      const cur = pos.get(id)!;
      pos.set(id, [
        Math.min(Math.max(cur[0] + limited[0], 0), W),
        Math.min(Math.max(cur[1] + limited[1], 0), H),
      ]);
    }
    temp -= cool;
  }

  return ids.map(id => ({ id, x: pos.get(id)![0], y: pos.get(id)![1] }));
}
