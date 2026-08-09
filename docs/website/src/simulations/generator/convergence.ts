// Deterministic Lloyd's-algorithm (k-means) generator — a framework-neutral
// stand-in illustrating what happens *conceptually* behind pgvector's ANN
// index building (backend/src/database/image_database.py) without touching
// real embeddings. Pure functions + a generator; the Aurelia island
// (src/frameworks/aurelia/ann-convergence-app.ts) is the only consumer that
// knows how to draw it.
import type { Centroid, ClusterAssignment, ConvergenceFrame, Point2D } from "../repository/types";

/** Mulberry32 — tiny seeded PRNG so the sim is reproducible across renders. */
function mulberry32(seed: number) {
  let a = seed;
  return function next() {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function distanceSquared(a: Point2D, b: Point2D): number {
  return (a.x - b.x) ** 2 + (a.y - b.y) ** 2;
}

function nearestCentroid(point: Point2D, centroids: Centroid[]): Centroid {
  let best = centroids[0];
  let bestDist = Infinity;
  for (const c of centroids) {
    const d = distanceSquared(point, c);
    if (d < bestDist) {
      bestDist = d;
      best = c;
    }
  }
  return best;
}

function recomputeCentroids(assignments: ClusterAssignment[], prev: Centroid[]): Centroid[] {
  return prev.map((c) => {
    const members = assignments.filter((a) => a.centroidId === c.id).map((a) => a.point);
    if (!members.length) return c;
    const x = members.reduce((sum, p) => sum + p.x, 0) / members.length;
    const y = members.reduce((sum, p) => sum + p.y, 0) / members.length;
    return { id: c.id, x, y };
  });
}

export interface ConvergenceGeneratorOptions {
  seed: number;
  pointCount: number;
  clusterCount: number;
  maxSteps: number;
  /** Centroid movement below this threshold (summed) is treated as converged. */
  epsilon?: number;
}

export function* generateConvergence(opts: ConvergenceGeneratorOptions): Generator<ConvergenceFrame> {
  const { seed, pointCount, clusterCount, maxSteps, epsilon = 0.15 } = opts;
  const rand = mulberry32(seed);
  const width = 100;
  const height = 100;

  const points: Point2D[] = Array.from({ length: pointCount }, () => ({
    x: rand() * width,
    y: rand() * height,
  }));

  let centroids: Centroid[] = Array.from({ length: clusterCount }, (_, id) => ({
    id,
    x: rand() * width,
    y: rand() * height,
  }));

  for (let step = 0; step < maxSteps; step++) {
    const assignments: ClusterAssignment[] = points.map((point) => ({
      point,
      centroidId: nearestCentroid(point, centroids).id,
    }));

    const inertia = assignments.reduce((sum, a) => {
      const c = centroids.find((c) => c.id === a.centroidId)!;
      return sum + distanceSquared(a.point, c);
    }, 0);

    const nextCentroids = recomputeCentroids(assignments, centroids);
    const movement = nextCentroids.reduce(
      (sum, c, i) => sum + Math.sqrt(distanceSquared(c, centroids[i])),
      0
    );
    const converged = movement < epsilon;

    yield { step, centroids, assignments, inertia, converged };

    centroids = nextCentroids;
    if (converged) return;
  }
}
