//! Descriptive statistics and distribution summaries for the analytics backbone.
//!
//! Used by Phase 4 (failure mode clustering, causal discovery inputs) and
//! Phase 2.3 (weight/gradient trajectory summarisation).

// ── Core statistics ──────────────────────────────────────────────────────────

/// Arithmetic mean. Returns `f64::NAN` for empty input.
///
/// # Examples
///
/// ```
/// # use base::math::stats::mean;
/// assert_eq!(mean(&[1.0, 2.0, 3.0]), 2.0);
/// assert!(mean(&[]).is_nan());
/// ```
pub fn mean(xs: &[f64]) -> f64 {
    if xs.is_empty() { return f64::NAN; }
    xs.iter().sum::<f64>() / xs.len() as f64
}

/// Population variance (`1/n` denominator).
///
/// Returns `0.0` for slices with fewer than 2 elements.
///
/// # Examples
///
/// ```
/// # use base::math::stats::variance;
/// assert!((variance(&[2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]) - 4.0).abs() < 1e-10);
/// assert_eq!(variance(&[42.0]), 0.0);
/// ```
pub fn variance(xs: &[f64]) -> f64 {
    if xs.len() < 2 { return 0.0; }
    let m = mean(xs);
    xs.iter().map(|&x| (x - m).powi(2)).sum::<f64>() / xs.len() as f64
}

/// Sample variance (`1/(n-1)` denominator).
///
/// Returns `0.0` for slices with fewer than 2 elements.
///
/// # Examples
///
/// ```
/// # use base::math::stats::sample_variance;
/// assert!((sample_variance(&[2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]) - 4.571428).abs() < 1e-5);
/// ```
pub fn sample_variance(xs: &[f64]) -> f64 {
    if xs.len() < 2 { return 0.0; }
    let m = mean(xs);
    xs.iter().map(|&x| (x - m).powi(2)).sum::<f64>() / (xs.len() - 1) as f64
}

/// Population standard deviation.
///
/// # Examples
///
/// ```
/// # use base::math::stats::std_dev;
/// assert!((std_dev(&[2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]) - 2.0).abs() < 1e-10);
/// ```
pub fn std_dev(xs: &[f64]) -> f64 { variance(xs).sqrt() }

/// Sample standard deviation.
///
/// # Examples
///
/// ```
/// # use base::math::stats::sample_std_dev;
/// // Sample std-dev of a two-element series with mean 5.0
/// assert!((sample_std_dev(&[3.0, 7.0]) - (8.0f64).sqrt()).abs() < 1e-10);
/// assert_eq!(sample_std_dev(&[42.0]), 0.0);
/// ```
pub fn sample_std_dev(xs: &[f64]) -> f64 { sample_variance(xs).sqrt() }

/// Population covariance of two equal-length series.
///
/// # Examples
///
/// ```
/// # use base::math::stats::covariance;
/// // xs and ys move together → positive covariance
/// assert!(covariance(&[1.0, 2.0, 3.0], &[4.0, 5.0, 6.0]) > 0.0);
/// // xs and ys move oppositely → negative covariance
/// assert!(covariance(&[1.0, 2.0, 3.0], &[6.0, 5.0, 4.0]) < 0.0);
/// // constant ys → covariance = 0
/// assert_eq!(covariance(&[1.0, 2.0, 3.0], &[5.0, 5.0, 5.0]), 0.0);
/// ```
pub fn covariance(xs: &[f64], ys: &[f64]) -> f64 {
    assert_eq!(xs.len(), ys.len(), "series must have equal length");
    if xs.is_empty() { return 0.0; }
    let mx = mean(xs);
    let my = mean(ys);
    xs.iter().zip(ys).map(|(&x, &y)| (x - mx) * (y - my)).sum::<f64>() / xs.len() as f64
}

/// Pearson correlation coefficient ∈ [-1, 1].
///
/// Returns `0.0` if either series is constant (zero standard deviation).
///
/// # Examples
///
/// ```
/// # use base::math::stats::pearson_correlation;
/// // Perfect positive correlation
/// assert!((pearson_correlation(&[1.0, 2.0, 3.0], &[4.0, 5.0, 6.0]) - 1.0).abs() < 1e-10);
/// // Perfect negative correlation
/// assert!((pearson_correlation(&[1.0, 2.0, 3.0], &[6.0, 5.0, 4.0]) + 1.0).abs() < 1e-10);
/// ```
pub fn pearson_correlation(xs: &[f64], ys: &[f64]) -> f64 {
    let sx = std_dev(xs);
    let sy = std_dev(ys);
    if sx == 0.0 || sy == 0.0 { return 0.0; }
    covariance(xs, ys) / (sx * sy)
}

/// Minimum value. Returns `f64::INFINITY` for empty input.
///
/// # Examples
///
/// ```
/// # use base::math::stats::min;
/// assert_eq!(min(&[3.0, 1.0, 4.0, 1.0, 5.0]), 1.0);
/// assert!(min(&[]).is_infinite());
/// ```
pub fn min(xs: &[f64]) -> f64 {
    xs.iter().cloned().fold(f64::INFINITY, f64::min)
}

/// Maximum value. Returns `f64::NEG_INFINITY` for empty input.
///
/// # Examples
///
/// ```
/// # use base::math::stats::max;
/// assert_eq!(max(&[3.0, 1.0, 4.0, 1.0, 5.0]), 5.0);
/// assert!(max(&[]).is_infinite());
/// ```
pub fn max(xs: &[f64]) -> f64 {
    xs.iter().cloned().fold(f64::NEG_INFINITY, f64::max)
}

/// Interquartile range (Q3 - Q1) via nearest-rank percentile.
///
/// # Examples
///
/// ```
/// # use base::math::stats::iqr;
/// // [1..10]: Q1=3, Q3=8 (nearest rank on 10 values)
/// let xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0];
/// assert!(iqr(&xs) > 0.0);
/// // Constant series → IQR = 0
/// assert_eq!(iqr(&[7.0, 7.0, 7.0]), 0.0);
/// ```
pub fn iqr(xs: &[f64]) -> f64 {
    percentile(xs, 0.75) - percentile(xs, 0.25)
}

/// Nearest-rank percentile. `p` ∈ [0, 1].
///
/// Returns `f64::NAN` for empty input.
///
/// # Examples
///
/// ```
/// # use base::math::stats::percentile;
/// let xs = [1.0, 2.0, 3.0, 4.0, 5.0];
/// assert_eq!(percentile(&xs, 0.0), 1.0);
/// assert_eq!(percentile(&xs, 1.0), 5.0);
/// assert_eq!(percentile(&xs, 0.5), 3.0);
/// ```
pub fn percentile(xs: &[f64], p: f64) -> f64 {
    if xs.is_empty() { return f64::NAN; }
    let mut sorted = xs.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let idx = ((p * (sorted.len() - 1) as f64).round() as usize).min(sorted.len() - 1);
    sorted[idx]
}

/// Median (50th percentile).
///
/// # Examples
///
/// ```
/// # use base::math::stats::median;
/// assert_eq!(median(&[3.0, 1.0, 4.0, 1.0, 5.0]), 3.0);
/// ```
pub fn median(xs: &[f64]) -> f64 { percentile(xs, 0.50) }

// ── Normalisation ────────────────────────────────────────────────────────────

/// Map each value to z-score: `(x - mean) / std_dev`.  Returns zeros for
/// constant series.
///
/// # Examples
///
/// ```
/// # use base::math::stats::z_score_normalize;
/// let z = z_score_normalize(&[0.0, 10.0]);
/// assert!(z[0] < 0.0 && z[1] > 0.0);
/// assert!((z[0] + z[1]).abs() < 1e-12);
/// // Constant series → all zeros
/// assert_eq!(z_score_normalize(&[5.0, 5.0, 5.0]), vec![0.0, 0.0, 0.0]);
/// ```
pub fn z_score_normalize(xs: &[f64]) -> Vec<f64> {
    let m = mean(xs);
    let s = std_dev(xs);
    if s == 0.0 { return vec![0.0; xs.len()]; }
    xs.iter().map(|&x| (x - m) / s).collect()
}

/// Min-max normalise to `[0, 1]`.  Returns zeros for constant series.
///
/// # Examples
///
/// ```
/// # use base::math::stats::min_max_normalize;
/// let n = min_max_normalize(&[2.0, 5.0, 8.0]);
/// assert_eq!(n[0], 0.0);
/// assert_eq!(n[2], 1.0);
/// // Constant series → all zeros
/// assert_eq!(min_max_normalize(&[3.0, 3.0, 3.0]), vec![0.0, 0.0, 0.0]);
/// ```
pub fn min_max_normalize(xs: &[f64]) -> Vec<f64> {
    let lo = min(xs);
    let hi = max(xs);
    let range = hi - lo;
    if range == 0.0 { return vec![0.0; xs.len()]; }
    xs.iter().map(|&x| (x - lo) / range).collect()
}

// ── Histogram ────────────────────────────────────────────────────────────────

/// Equal-width histogram. Returns `(bin_edges, counts)` where `bin_edges` has
/// `bins + 1` elements. Values outside `[lo, hi]` are clamped into the
/// outermost bins.
///
/// # Examples
///
/// ```
/// # use base::math::stats::histogram;
/// let xs: Vec<f64> = (0..100).map(|i| i as f64).collect();
/// let (edges, counts) = histogram(&xs, 10);
/// assert_eq!(edges.len(), 11);
/// assert_eq!(counts.iter().sum::<usize>(), 100);
/// // Single unique value → all counts in the first bin
/// let (_, c) = histogram(&[5.0, 5.0, 5.0], 4);
/// assert_eq!(c.iter().sum::<usize>(), 3);
/// ```
pub fn histogram(xs: &[f64], bins: usize) -> (Vec<f64>, Vec<usize>) {
    assert!(bins > 0);
    let lo = min(xs);
    let hi = max(xs);
    let range = hi - lo;
    let mut counts = vec![0usize; bins];
    let mut edges = Vec::with_capacity(bins + 1);
    for i in 0..=bins {
        edges.push(lo + range * i as f64 / bins as f64);
    }
    for &x in xs {
        let bin = if range == 0.0 {
            0
        } else {
            ((x - lo) / range * bins as f64) as usize
        };
        counts[bin.min(bins - 1)] += 1;
    }
    (edges, counts)
}

/// Convert raw counts to a normalised probability distribution summing to 1.
///
/// # Examples
///
/// ```
/// # use base::math::stats::counts_to_probs;
/// let probs = counts_to_probs(&[1, 1, 2]);
/// assert!((probs[0] - 0.25).abs() < 1e-10);
/// assert!((probs[2] - 0.50).abs() < 1e-10);
/// // Zero total → all zeros
/// assert_eq!(counts_to_probs(&[0, 0]), vec![0.0, 0.0]);
/// ```
pub fn counts_to_probs(counts: &[usize]) -> Vec<f64> {
    let total: usize = counts.iter().sum();
    if total == 0 { return vec![0.0; counts.len()]; }
    counts.iter().map(|&c| c as f64 / total as f64).collect()
}

// ── Covariance matrix ────────────────────────────────────────────────────────

/// Compute the d×d covariance matrix for an n×d dataset.
/// Returns a flat row-major `Vec<f64>` of length `d*d`.
///
/// # Examples
///
/// ```
/// # use base::math::stats::covariance_matrix;
/// // Two observations of a 2-D variable: [0,0] and [2,2]
/// // Each dimension has variance 1.0; the cross-covariance is also 1.0.
/// let data = vec![vec![0.0, 0.0], vec![2.0, 2.0]];
/// let cov = covariance_matrix(&data);
/// assert_eq!(cov.len(), 4);           // 2×2 flattened
/// assert!((cov[0] - 1.0).abs() < 1e-10);  // Var(x) = 1.0
/// assert!((cov[3] - 1.0).abs() < 1e-10);  // Var(y) = 1.0
/// assert!((cov[1] - 1.0).abs() < 1e-10);  // Cov(x,y) = 1.0
/// // Empty dataset → empty output
/// assert!(covariance_matrix(&[]).is_empty());
/// ```
pub fn covariance_matrix(data: &[Vec<f64>]) -> Vec<f64> {
    if data.is_empty() { return vec![]; }
    let n = data.len();
    let d = data[0].len();
    let means: Vec<f64> = (0..d).map(|j| data.iter().map(|r| r[j]).sum::<f64>() / n as f64).collect();
    let mut cov = vec![0.0f64; d * d];
    for row in data {
        for j in 0..d {
            for k in 0..d {
                cov[j * d + k] += (row[j] - means[j]) * (row[k] - means[k]);
            }
        }
    }
    cov.iter_mut().for_each(|v| *v /= n as f64);
    cov
}

// ── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mean() {
        assert_eq!(mean(&[1.0, 2.0, 3.0]), 2.0);
    }

    #[test]
    fn test_variance() {
        // population variance of [2,4,4,4,5,5,7,9] = 4.0
        let xs = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0];
        assert!((variance(&xs) - 4.0).abs() < 1e-10);
    }

    #[test]
    fn test_pearson_perfect_correlation() {
        let xs: Vec<f64> = (0..10).map(|i| i as f64).collect();
        let ys: Vec<f64> = xs.iter().map(|&x| 2.0 * x + 3.0).collect();
        assert!((pearson_correlation(&xs, &ys) - 1.0).abs() < 1e-12);
    }

    #[test]
    fn test_percentile_median() {
        let xs = [1.0, 3.0, 5.0, 7.0, 9.0];
        assert_eq!(median(&xs), 5.0);
    }

    #[test]
    fn test_z_score() {
        let xs = [0.0, 10.0];
        let z = z_score_normalize(&xs);
        assert!(z[0] < 0.0);
        assert!(z[1] > 0.0);
        assert!((z[0] + z[1]).abs() < 1e-12);
    }

    #[test]
    fn test_min_max_normalize() {
        let xs = [2.0, 5.0, 8.0];
        let n = min_max_normalize(&xs);
        assert_eq!(n[0], 0.0);
        assert_eq!(n[2], 1.0);
    }

    #[test]
    fn test_histogram_bins() {
        let xs: Vec<f64> = (0..100).map(|i| i as f64).collect();
        let (edges, counts) = histogram(&xs, 10);
        assert_eq!(edges.len(), 11);
        assert_eq!(counts.iter().sum::<usize>(), 100);
    }

    #[test]
    fn test_iqr() {
        let xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0];
        let q = iqr(&xs);
        assert!(q > 0.0);
    }
}
