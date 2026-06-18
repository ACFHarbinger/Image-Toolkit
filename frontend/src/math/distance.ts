/** Distance and similarity metrics for the analytics frontend.
 *
 *  Used by the software-cartography scatter view (Phase 1.3) and failure
 *  clustering visualisations (Phase 4.4). */

/** Squared Euclidean distance — cheaper when only relative ordering matters. */
export const squaredEuclidean = (a: number[], b: number[]): number =>
  a.reduce((acc, ai, i) => acc + (ai - b[i]) ** 2, 0);

export const euclidean = (a: number[], b: number[]): number =>
  Math.sqrt(squaredEuclidean(a, b));

export const manhattan = (a: number[], b: number[]): number =>
  a.reduce((acc, ai, i) => acc + Math.abs(ai - b[i]), 0);

export const chebyshev = (a: number[], b: number[]): number =>
  a.reduce((acc, ai, i) => Math.max(acc, Math.abs(ai - b[i])), 0);

/** Cosine similarity ∈ [-1, 1].  Returns 0 for zero vectors. */
export const cosineSimilarity = (a: number[], b: number[]): number => {
  const dot = a.reduce((acc, ai, i) => acc + ai * b[i], 0);
  const na = Math.sqrt(a.reduce((acc, x) => acc + x * x, 0));
  const nb = Math.sqrt(b.reduce((acc, x) => acc + x * x, 0));
  return na === 0 || nb === 0 ? 0 : dot / (na * nb);
};

export const cosineDistance = (a: number[], b: number[]): number =>
  1 - cosineSimilarity(a, b);

/** Hamming distance: count of positions where values differ. */
export const hammingDistance = (a: number[], b: number[]): number =>
  a.reduce((acc, ai, i) => acc + (ai !== b[i] ? 1 : 0), 0);

/** Full n×n pairwise distance matrix. */
export function pairwiseDistances(
  points: number[][],
  distFn: (a: number[], b: number[]) => number = euclidean,
): number[][] {
  const n = points.length;
  const mat: number[][] = Array.from({ length: n }, () => new Array<number>(n).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const d = distFn(points[i], points[j]);
      mat[i][j] = d;
      mat[j][i] = d;
    }
  }
  return mat;
}

/** Condensed upper-triangle distance vector (compatible with scipy linkage input). */
export function condensedDistances(
  points: number[][],
  distFn: (a: number[], b: number[]) => number = euclidean,
): number[] {
  const n = points.length;
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      out.push(distFn(points[i], points[j]));
    }
  }
  return out;
}
