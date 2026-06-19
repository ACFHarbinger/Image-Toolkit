//! Distance and similarity metrics for the analytics backbone.
//!
//! Powers Phase 1.3 (software cartography MDS stress), Phase 4.4 (K-Means /
//! DBSCAN cluster assignment), and Phase 10 (Vietoris-Rips filtration radii).

// ── Point-pair distances ─────────────────────────────────────────────────────

/// Squared Euclidean distance (cheaper than Euclidean when relative ordering suffices).
///
/// # Examples
///
/// ```
/// # use base::math::distance::squared_euclidean;
/// assert_eq!(squared_euclidean(&[0.0, 0.0], &[3.0, 4.0]), 25.0);
/// assert_eq!(squared_euclidean(&[1.0], &[1.0]), 0.0);
/// ```
#[inline]
pub fn squared_euclidean(a: &[f64], b: &[f64]) -> f64 {
    a.iter().zip(b).map(|(&ai, &bi)| (ai - bi).powi(2)).sum()
}

/// Euclidean (L2) distance.
///
/// # Examples
///
/// ```
/// # use base::math::distance::euclidean;
/// assert!((euclidean(&[0.0, 0.0], &[3.0, 4.0]) - 5.0).abs() < 1e-10);
/// assert_eq!(euclidean(&[1.0], &[1.0]), 0.0);
/// ```
#[inline]
pub fn euclidean(a: &[f64], b: &[f64]) -> f64 {
    squared_euclidean(a, b).sqrt()
}

/// Manhattan (L1) distance.
///
/// # Examples
///
/// ```
/// # use base::math::distance::manhattan;
/// assert_eq!(manhattan(&[0.0, 0.0], &[3.0, 4.0]), 7.0);
/// assert_eq!(manhattan(&[1.0, 1.0], &[1.0, 1.0]), 0.0);
/// ```
#[inline]
pub fn manhattan(a: &[f64], b: &[f64]) -> f64 {
    a.iter().zip(b).map(|(&ai, &bi)| (ai - bi).abs()).sum()
}

/// Chebyshev (L∞) distance.
///
/// # Examples
///
/// ```
/// # use base::math::distance::chebyshev;
/// assert_eq!(chebyshev(&[0.0, 0.0], &[3.0, 4.0]), 4.0);
/// ```
#[inline]
pub fn chebyshev(a: &[f64], b: &[f64]) -> f64 {
    a.iter().zip(b).map(|(&ai, &bi)| (ai - bi).abs()).fold(0.0f64, f64::max)
}

/// Minkowski distance with exponent `p`.
///
/// `p = 1` → Manhattan, `p = 2` → Euclidean, `p → ∞` → Chebyshev.
///
/// # Panics
///
/// Panics if `p < 1`.
///
/// # Examples
///
/// ```
/// # use base::math::distance::{minkowski, euclidean, manhattan};
/// let a = [0.0, 0.0];
/// let b = [3.0, 4.0];
/// assert!((minkowski(&a, &b, 2.0) - euclidean(&a, &b)).abs() < 1e-10);
/// assert!((minkowski(&a, &b, 1.0) - manhattan(&a, &b)).abs() < 1e-10);
/// ```
pub fn minkowski(a: &[f64], b: &[f64], p: f64) -> f64 {
    assert!(p >= 1.0, "Minkowski p must be ≥ 1");
    let sum: f64 = a.iter().zip(b).map(|(&ai, &bi)| (ai - bi).abs().powf(p)).sum();
    sum.powf(1.0 / p)
}

// ── Cosine ───────────────────────────────────────────────────────────────────

/// Cosine similarity ∈ [-1, 1].  Returns 0 for zero vectors.
///
/// # Examples
///
/// ```
/// # use base::math::distance::cosine_similarity;
/// // Identical vectors → similarity = 1
/// assert!((cosine_similarity(&[1.0, 0.0], &[1.0, 0.0]) - 1.0).abs() < 1e-10);
/// // Orthogonal vectors → similarity = 0
/// assert!((cosine_similarity(&[1.0, 0.0], &[0.0, 1.0])).abs() < 1e-10);
/// // Zero vector → 0 by convention
/// assert_eq!(cosine_similarity(&[0.0, 0.0], &[1.0, 2.0]), 0.0);
/// ```
pub fn cosine_similarity(a: &[f64], b: &[f64]) -> f64 {
    let dot: f64 = a.iter().zip(b).map(|(&ai, &bi)| ai * bi).sum();
    let na: f64 = a.iter().map(|&x| x * x).sum::<f64>().sqrt();
    let nb: f64 = b.iter().map(|&x| x * x).sum::<f64>().sqrt();
    if na == 0.0 || nb == 0.0 { 0.0 } else { dot / (na * nb) }
}

/// Cosine distance = 1 − cosine_similarity, ∈ [0, 2].
///
/// # Examples
///
/// ```
/// # use base::math::distance::cosine_distance;
/// assert!((cosine_distance(&[1.0, 0.0], &[1.0, 0.0])).abs() < 1e-10);
/// assert!((cosine_distance(&[1.0, 0.0], &[0.0, 1.0]) - 1.0).abs() < 1e-10);
/// ```
#[inline]
pub fn cosine_distance(a: &[f64], b: &[f64]) -> f64 {
    1.0 - cosine_similarity(a, b)
}

// ── Discrete / bitstring ─────────────────────────────────────────────────────

/// Hamming distance: number of positions where values differ.
pub fn hamming_distance(a: &[u8], b: &[u8]) -> usize {
    assert_eq!(a.len(), b.len());
    a.iter().zip(b).filter(|(ai, bi)| ai != bi).count()
}

/// Hamming distance on boolean/0-1 float vectors (treats non-zero as 1).
pub fn hamming_f64(a: &[f64], b: &[f64]) -> usize {
    assert_eq!(a.len(), b.len());
    a.iter().zip(b).filter(|(&ai, &bi)| (ai != 0.0) != (bi != 0.0)).count()
}

// ── Histogram / distribution ─────────────────────────────────────────────────

/// Bhattacharyya coefficient `BC(P, Q) = Σ sqrt(P_i · Q_i)`.
///
/// Measures distributional overlap; 1 = identical, 0 = disjoint.
pub fn bhattacharyya_coefficient(p: &[f64], q: &[f64]) -> f64 {
    let p_sum: f64 = p.iter().sum();
    let q_sum: f64 = q.iter().sum();
    if p_sum == 0.0 || q_sum == 0.0 { return 0.0; }
    p.iter().zip(q)
        .map(|(&pi, &qi)| ((pi / p_sum) * (qi / q_sum)).sqrt())
        .sum()
}

/// Bhattacharyya distance `D_B = -ln(BC)`.  Returns `f64::INFINITY` for
/// completely disjoint distributions.
pub fn bhattacharyya_distance(p: &[f64], q: &[f64]) -> f64 {
    let bc = bhattacharyya_coefficient(p, q);
    if bc == 0.0 { f64::INFINITY } else { -bc.ln() }
}

/// Hellinger distance `H(P, Q) = sqrt(1 - BC)` ∈ [0, 1].
pub fn hellinger_distance(p: &[f64], q: &[f64]) -> f64 {
    (1.0 - bhattacharyya_coefficient(p, q)).max(0.0).sqrt()
}

// ── Pairwise distance matrices ────────────────────────────────────────────────

/// Compute the full n×n pairwise distance matrix.
///
/// `dist_fn` must be symmetric (the matrix is filled in both triangles for
/// O(n²/2) calls using symmetry).
pub fn pairwise_distance_matrix(
    points: &[Vec<f64>],
    dist_fn: impl Fn(&[f64], &[f64]) -> f64,
) -> Vec<Vec<f64>> {
    let n = points.len();
    let mut mat = vec![vec![0.0f64; n]; n];
    for i in 0..n {
        for j in (i + 1)..n {
            let d = dist_fn(&points[i], &points[j]);
            mat[i][j] = d;
            mat[j][i] = d;
        }
    }
    mat
}

/// Compute only the upper triangle (row-major flattened, length `n*(n-1)/2`).
///
/// Useful when feeding directly into Ripser / Gudhi for persistent homology
/// (Phase 10).
pub fn condensed_distance_matrix(
    points: &[Vec<f64>],
    dist_fn: impl Fn(&[f64], &[f64]) -> f64,
) -> Vec<f64> {
    let n = points.len();
    let mut out = Vec::with_capacity(n * (n - 1) / 2);
    for i in 0..n {
        for j in (i + 1)..n {
            out.push(dist_fn(&points[i], &points[j]));
        }
    }
    out
}

// ── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_euclidean_pythagorean() {
        assert!((euclidean(&[0.0, 0.0], &[3.0, 4.0]) - 5.0).abs() < 1e-10);
    }

    #[test]
    fn test_manhattan() {
        assert_eq!(manhattan(&[0.0, 0.0], &[1.0, 1.0]), 2.0);
    }

    #[test]
    fn test_cosine_identical() {
        let v = vec![1.0, 2.0, 3.0];
        assert!((cosine_similarity(&v, &v) - 1.0).abs() < 1e-12);
    }

    #[test]
    fn test_cosine_orthogonal() {
        let a = vec![1.0, 0.0];
        let b = vec![0.0, 1.0];
        assert!(cosine_similarity(&a, &b).abs() < 1e-12);
    }

    #[test]
    fn test_bhattacharyya_identical() {
        let p = [0.2, 0.5, 0.3];
        assert!((bhattacharyya_coefficient(&p, &p) - 1.0).abs() < 1e-10);
        assert!(bhattacharyya_distance(&p, &p) < 1e-10);
    }

    #[test]
    fn test_bhattacharyya_disjoint() {
        let p = [1.0, 0.0];
        let q = [0.0, 1.0];
        assert_eq!(bhattacharyya_coefficient(&p, &q), 0.0);
        assert!(bhattacharyya_distance(&p, &q).is_infinite());
    }

    #[test]
    fn test_hamming() {
        let a = [1u8, 0, 1, 1, 0];
        let b = [0u8, 0, 1, 0, 0];
        assert_eq!(hamming_distance(&a, &b), 2);
    }

    #[test]
    fn test_pairwise_matrix_symmetry() {
        let pts = vec![vec![0.0, 0.0], vec![1.0, 0.0], vec![0.0, 1.0]];
        let mat = pairwise_distance_matrix(&pts, euclidean);
        assert_eq!(mat[0][0], 0.0);
        assert!((mat[0][1] - mat[1][0]).abs() < 1e-12);
        assert!((mat[1][2] - mat[2][1]).abs() < 1e-12);
    }

    #[test]
    fn test_condensed_length() {
        let pts: Vec<Vec<f64>> = (0..5).map(|i| vec![i as f64]).collect();
        let c = condensed_distance_matrix(&pts, euclidean);
        assert_eq!(c.len(), 5 * 4 / 2);
    }
}
