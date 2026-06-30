/**
 * @packageDocumentation
 * @module distance
 * Distance and similarity metrics for the analytics frontend.
 *
 * Used by the software-cartography scatter view (Phase 1.3) and failure
 * clustering visualisations (Phase 4.4).
 *
 * @category Distance
 */

/**
 * Squared Euclidean distance — cheaper than `euclidean` when only relative
 * ordering matters (avoids the square root).
 * @param a - First vector.
 * @param b - Second vector. Must have the same length as `a`.
 * @returns Sum of squared element-wise differences ≥ 0.
 * @example
 * ```ts
 * squaredEuclidean([0, 0], [3, 4]); // 25
 * ```
 */
export const squaredEuclidean = (a: number[], b: number[]): number =>
  a.reduce((acc, ai, i) => acc + (ai - b[i]) ** 2, 0);

/**
 * Euclidean (L2) distance.
 * @param a - First vector.
 * @param b - Second vector. Must have the same length as `a`.
 * @returns L2 distance ≥ 0.
 * @example
 * ```ts
 * euclidean([0, 0], [3, 4]); // 5
 * ```
 */
export const euclidean = (a: number[], b: number[]): number =>
  Math.sqrt(squaredEuclidean(a, b));

/**
 * Manhattan (L1 / city-block) distance.
 * @param a - First vector.
 * @param b - Second vector. Must have the same length as `a`.
 * @returns L1 distance ≥ 0.
 */
export const manhattan = (a: number[], b: number[]): number =>
  a.reduce((acc, ai, i) => acc + Math.abs(ai - b[i]), 0);

/**
 * Chebyshev (L∞ / chessboard) distance.
 * @param a - First vector.
 * @param b - Second vector. Must have the same length as `a`.
 * @returns Maximum absolute element-wise difference ≥ 0.
 */
export const chebyshev = (a: number[], b: number[]): number =>
  a.reduce((acc, ai, i) => Math.max(acc, Math.abs(ai - b[i])), 0);

/**
 * Cosine similarity ∈ [−1, 1].
 * Returns 0 for zero vectors (no meaningful angle).
 * @param a - First vector.
 * @param b - Second vector. Must have the same length as `a`.
 * @returns Cosine similarity ∈ [−1, 1].
 * @example
 * ```ts
 * cosineSimilarity([1, 0], [1, 0]); // 1.0 (identical direction)
 * cosineSimilarity([1, 0], [0, 1]); // 0.0 (orthogonal)
 * cosineSimilarity([1, 0], [-1, 0]); // -1.0 (opposite)
 * ```
 */
export const cosineSimilarity = (a: number[], b: number[]): number => {
  const dot = a.reduce((acc, ai, i) => acc + ai * b[i], 0);
  const na = Math.sqrt(a.reduce((acc, x) => acc + x * x, 0));
  const nb = Math.sqrt(b.reduce((acc, x) => acc + x * x, 0));
  return na === 0 || nb === 0 ? 0 : dot / (na * nb);
};

/**
 * Cosine distance = 1 − `cosineSimilarity`. ∈ [0, 2].
 * @param a - First vector.
 * @param b - Second vector. Must have the same length as `a`.
 * @returns Cosine distance ∈ [0, 2].
 */
export const cosineDistance = (a: number[], b: number[]): number =>
  1 - cosineSimilarity(a, b);

/**
 * Hamming distance: count of positions where values differ.
 * Suitable for binary or integer vectors.
 * @param a - First vector.
 * @param b - Second vector. Must have the same length as `a`.
 * @returns Number of differing positions ∈ [0, a.length].
 * @example
 * ```ts
 * hammingDistance([1, 0, 1], [1, 1, 1]); // 1
 * ```
 */
export const hammingDistance = (a: number[], b: number[]): number =>
  a.reduce((acc, ai, i) => acc + (ai !== b[i] ? 1 : 0), 0);

/**
 * Compute the full N×N pairwise distance matrix.
 * The matrix is symmetric with zeros on the diagonal.
 * @param points - Array of N vectors (all must have the same dimensionality).
 * @param distFn - Distance function to apply. Defaults to `euclidean`.
 * @returns N×N matrix where `result[i][j]` is the distance between `points[i]` and `points[j]`.
 * @example
 * ```ts
 * pairwiseDistances([[0, 0], [3, 4], [0, 4]]);
 * // [[0, 5, 4], [5, 0, 3], [4, 3, 0]]
 * ```
 */
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

/**
 * Condensed upper-triangle distance vector.
 * Compatible with SciPy `linkage` input format (row-major upper triangle, no diagonal).
 * @param points - Array of N vectors.
 * @param distFn - Distance function to apply. Defaults to `euclidean`.
 * @returns Array of N*(N-1)/2 distances in row-major upper-triangle order.
 * @example
 * ```ts
 * // For 3 points → [d(0,1), d(0,2), d(1,2)]
 * condensedDistances([[0,0],[1,0],[0,1]]).length; // 3
 * ```
 */
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
