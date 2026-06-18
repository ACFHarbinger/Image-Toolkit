/** Descriptive statistics for the analytics dashboard (Phase 4 charts,
 *  Phase 2.3 gradient histograms). */

export const mean = (xs: number[]): number =>
  xs.length === 0 ? NaN : xs.reduce((a, b) => a + b, 0) / xs.length;

export const variance = (xs: number[]): number => {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return xs.reduce((acc, x) => acc + (x - m) ** 2, 0) / xs.length;
};

export const sampleVariance = (xs: number[]): number => {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return xs.reduce((acc, x) => acc + (x - m) ** 2, 0) / (xs.length - 1);
};

export const stdDev = (xs: number[]): number => Math.sqrt(variance(xs));
export const sampleStdDev = (xs: number[]): number => Math.sqrt(sampleVariance(xs));

export const min = (xs: number[]): number => Math.min(...xs);
export const max = (xs: number[]): number => Math.max(...xs);

/** Nearest-rank percentile. `p` ∈ [0, 1]. */
export const percentile = (xs: number[], p: number): number => {
  if (xs.length === 0) return NaN;
  const sorted = [...xs].sort((a, b) => a - b);
  const idx = Math.round(p * (sorted.length - 1));
  return sorted[Math.min(idx, sorted.length - 1)];
};

export const median = (xs: number[]): number => percentile(xs, 0.5);

export const iqr = (xs: number[]): number => percentile(xs, 0.75) - percentile(xs, 0.25);

/** Pearson correlation coefficient ∈ [-1, 1]. */
export const pearsonCorrelation = (xs: number[], ys: number[]): number => {
  const mx = mean(xs);
  const my = mean(ys);
  const sx = stdDev(xs);
  const sy = stdDev(ys);
  if (sx === 0 || sy === 0) return 0;
  const cov = xs.reduce((acc, x, i) => acc + (x - mx) * (ys[i] - my), 0) / xs.length;
  return cov / (sx * sy);
};

/** Min-max normalise to [0, 1]. */
export const normalize01 = (xs: number[]): number[] => {
  const lo = min(xs);
  const hi = max(xs);
  const range = hi - lo;
  return range === 0 ? xs.map(() => 0) : xs.map(x => (x - lo) / range);
};

/** Z-score normalise. */
export const zScoreNormalize = (xs: number[]): number[] => {
  const m = mean(xs);
  const s = stdDev(xs);
  return s === 0 ? xs.map(() => 0) : xs.map(x => (x - m) / s);
};

export interface HistogramResult {
  edges: number[];
  counts: number[];
  probs: number[];
}

/** Equal-width histogram. Returns bin edges (length bins+1), counts, and probs. */
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
