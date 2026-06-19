/**
 * @packageDocumentation
 * @module stats
 * Descriptive statistics for the analytics dashboard (Phase 4 charts,
 * Phase 2.3 gradient histograms).
 *
 * @category Statistics
 */

/**
 * Arithmetic mean of a number array.
 * @param xs - Input values. Must be non-empty or NaN is returned.
 * @returns Mean, or `NaN` for empty input.
 * @example
 * ```ts
 * mean([1, 2, 3]); // 2
 * mean([]);        // NaN
 * ```
 */
export const mean = (xs: number[]): number =>
  xs.length === 0 ? NaN : xs.reduce((a, b) => a + b, 0) / xs.length;

/**
 * Population variance (divides by N).
 * @param xs - Input values. Returns 0 for arrays with fewer than 2 elements.
 * @returns Population variance ≥ 0.
 * @example
 * ```ts
 * variance([2, 4, 4, 4, 5, 5, 7, 9]); // 4
 * ```
 */
export const variance = (xs: number[]): number => {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return xs.reduce((acc, x) => acc + (x - m) ** 2, 0) / xs.length;
};

/**
 * Sample variance (divides by N−1, Bessel-corrected).
 * @param xs - Input values. Returns 0 for arrays with fewer than 2 elements.
 * @returns Sample variance ≥ 0.
 */
export const sampleVariance = (xs: number[]): number => {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return xs.reduce((acc, x) => acc + (x - m) ** 2, 0) / (xs.length - 1);
};

/**
 * Population standard deviation (square root of `variance`).
 * @param xs - Input values.
 * @returns Population std dev ≥ 0.
 */
export const stdDev = (xs: number[]): number => Math.sqrt(variance(xs));

/**
 * Sample standard deviation (square root of `sampleVariance`).
 * @param xs - Input values.
 * @returns Sample std dev ≥ 0.
 */
export const sampleStdDev = (xs: number[]): number => Math.sqrt(sampleVariance(xs));

/**
 * Minimum value in the array.
 * @param xs - Input values.
 * @returns Minimum element.
 */
export const min = (xs: number[]): number => Math.min(...xs);

/**
 * Maximum value in the array.
 * @param xs - Input values.
 * @returns Maximum element.
 */
export const max = (xs: number[]): number => Math.max(...xs);

/**
 * Nearest-rank percentile (R-1 method).
 * @param xs - Input values (need not be sorted).
 * @param p - Percentile rank in [0, 1]. 0 → minimum, 0.5 → median, 1 → maximum.
 * @returns The value at the nearest-rank percentile, or `NaN` for empty input.
 * @example
 * ```ts
 * percentile([1, 2, 3, 4], 0.5); // 2 (nearest-rank median)
 * ```
 */
export const percentile = (xs: number[], p: number): number => {
  if (xs.length === 0) return NaN;
  const sorted = [...xs].sort((a, b) => a - b);
  const idx = Math.round(p * (sorted.length - 1));
  return sorted[Math.min(idx, sorted.length - 1)];
};

/**
 * Median (50th percentile, nearest-rank).
 * @param xs - Input values.
 * @returns Median value.
 */
export const median = (xs: number[]): number => percentile(xs, 0.5);

/**
 * Interquartile range (Q3 − Q1).
 * @param xs - Input values.
 * @returns IQR ≥ 0.
 */
export const iqr = (xs: number[]): number => percentile(xs, 0.75) - percentile(xs, 0.25);

/**
 * Pearson correlation coefficient ∈ [−1, 1].
 * Returns 0 when either array has zero standard deviation.
 * @param xs - First array of values.
 * @param ys - Second array of values. Must have the same length as `xs`.
 * @returns Pearson r ∈ [−1, 1], or 0 for constant inputs.
 * @example
 * ```ts
 * pearsonCorrelation([1, 2, 3], [1, 2, 3]); // ~1.0
 * pearsonCorrelation([1, 2, 3], [3, 2, 1]); // ~-1.0
 * ```
 */
export const pearsonCorrelation = (xs: number[], ys: number[]): number => {
  const mx = mean(xs);
  const my = mean(ys);
  const sx = stdDev(xs);
  const sy = stdDev(ys);
  if (sx === 0 || sy === 0) return 0;
  const cov = xs.reduce((acc, x, i) => acc + (x - mx) * (ys[i] - my), 0) / xs.length;
  return cov / (sx * sy);
};

/**
 * Min-max normalise to [0, 1].
 * Returns all-zeros for constant arrays (zero range).
 * @param xs - Input values.
 * @returns Array with each element rescaled to [0, 1].
 */
export const normalize01 = (xs: number[]): number[] => {
  const lo = min(xs);
  const hi = max(xs);
  const range = hi - lo;
  return range === 0 ? xs.map(() => 0) : xs.map(x => (x - lo) / range);
};

/**
 * Z-score normalise (subtract mean, divide by std dev).
 * Returns all-zeros for constant arrays.
 * @param xs - Input values.
 * @returns Array of z-scores (zero mean, unit variance).
 */
export const zScoreNormalize = (xs: number[]): number[] => {
  const m = mean(xs);
  const s = stdDev(xs);
  return s === 0 ? xs.map(() => 0) : xs.map(x => (x - m) / s);
};

/** Result object returned by {@link histogram}. */
export interface HistogramResult {
  /** Bin edge values, length = `bins + 1`. */
  edges: number[];
  /** Integer count per bin, length = `bins`. */
  counts: number[];
  /** Probability (count / total) per bin, length = `bins`. */
  probs: number[];
}

/**
 * Equal-width histogram.
 * @param xs - Input values.
 * @param bins - Number of equal-width bins.
 * @returns `{ edges, counts, probs }` — see {@link HistogramResult}.
 * @example
 * ```ts
 * const h = histogram([1, 2, 3, 4], 2);
 * // h.edges ≈ [1, 2.5, 4]
 * // h.counts = [2, 2]
 * ```
 */
export const histogram = (xs: number[], bins: number): HistogramResult => {
  const lo = min(xs);
  const hi = max(xs);
  const range = hi - lo;
  const counts = new Array<number>(bins).fill(0);
  const edges = Array.from({ length: bins + 1 }, (_, i) => lo + (range * i) / bins);

  for (const x of xs) {
    const bin = range === 0 ? 0 : Math.min(Math.floor(((x - lo) / range) * bins), bins - 1);
    counts[bin]++;
  }

  const total = xs.length;
  const probs = counts.map(c => (total === 0 ? 0 : c / total));
  return { edges, counts, probs };
};
