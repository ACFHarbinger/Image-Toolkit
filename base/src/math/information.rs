//! Information-theoretic measures for the analytics backbone.
//!
//! Implements Shannon entropy, KL divergence, Jensen-Shannon divergence, and
//! mutual information — the mathematical foundation for Phase 4.1 (pipeline
//! stage dependency analysis) and Phase 1.3 (software cartography via LSI).

const LOG2_E: f64 = std::f64::consts::LOG2_E;

// ── Entropy ──────────────────────────────────────────────────────────────────

/// Shannon entropy in bits: `H(X) = -Σ p·log₂(p)`.
///
/// Treats zero probabilities as contributing 0 to the sum (0 log 0 = 0 by
/// convention).  Input probabilities need not sum to 1 — they are normalised
/// internally.
///
/// # Examples
///
/// ```
/// # use base::math::information::shannon_entropy;
/// // Uniform distribution over 2 outcomes → 1 bit
/// assert!((shannon_entropy(&[1.0, 1.0]) - 1.0).abs() < 1e-10);
/// // Uniform over 4 outcomes → 2 bits
/// assert!((shannon_entropy(&[1.0, 1.0, 1.0, 1.0]) - 2.0).abs() < 1e-10);
/// // Degenerate distribution → 0 bits
/// assert_eq!(shannon_entropy(&[1.0, 0.0, 0.0]), 0.0);
/// // Zero input → 0
/// assert_eq!(shannon_entropy(&[0.0, 0.0]), 0.0);
/// ```
pub fn shannon_entropy(probs: &[f64]) -> f64 {
    let total: f64 = probs.iter().sum();
    if total == 0.0 { return 0.0; }
    probs.iter()
        .filter(|&&p| p > 0.0)
        .map(|&p| { let q = p / total; -q * q.log2() })
        .sum()
}

/// Entropy in nats (natural log base).
pub fn entropy_nats(probs: &[f64]) -> f64 {
    shannon_entropy(probs) / LOG2_E
}

/// Shannon entropy computed from raw event counts (normalises internally).
pub fn empirical_entropy(counts: &[usize]) -> f64 {
    let probs: Vec<f64> = counts.iter().map(|&c| c as f64).collect();
    shannon_entropy(&probs)
}

/// Joint entropy `H(X, Y)` from a 2-D count matrix (rows = X values, cols = Y).
pub fn joint_entropy(joint_counts: &[Vec<usize>]) -> f64 {
    let flat: Vec<f64> = joint_counts.iter().flat_map(|row| row.iter().map(|&c| c as f64)).collect();
    shannon_entropy(&flat)
}

/// Conditional entropy `H(Y|X) = H(X,Y) − H(X)`.
pub fn conditional_entropy(joint_counts: &[Vec<usize>]) -> f64 {
    let marginal_x: Vec<f64> = joint_counts.iter().map(|row| row.iter().sum::<usize>() as f64).collect();
    joint_entropy(joint_counts) - shannon_entropy(&marginal_x)
}

// ── Divergences ──────────────────────────────────────────────────────────────

/// KL divergence `KL(P ‖ Q)` in bits.
///
/// Returns `f64::INFINITY` if `Q[i] = 0` for any `i` where `P[i] > 0`.
/// Input vectors must have the same length and will be normalised internally.
///
/// # Examples
///
/// ```
/// # use base::math::information::kl_divergence;
/// // KL divergence of a distribution with itself is 0
/// assert!(kl_divergence(&[1.0, 1.0], &[1.0, 1.0]).abs() < 1e-10);
/// // Disjoint support → infinity
/// assert!(kl_divergence(&[1.0, 0.0], &[0.0, 1.0]).is_infinite());
/// ```
pub fn kl_divergence(p: &[f64], q: &[f64]) -> f64 {
    assert_eq!(p.len(), q.len(), "P and Q must have equal length");
    let p_sum: f64 = p.iter().sum();
    let q_sum: f64 = q.iter().sum();
    if p_sum == 0.0 { return 0.0; }
    p.iter().zip(q).map(|(&pi, &qi)| {
        let pn = pi / p_sum;
        let qn = qi / q_sum;
        if pn == 0.0 { 0.0 }
        else if qn == 0.0 { f64::INFINITY }
        else { pn * (pn / qn).log2() }
    }).sum()
}

/// Jensen-Shannon divergence `JSD(P ‖ Q)` ∈ [0, 1] (bits, bounded by 1 for
/// disjoint distributions).  Symmetric and always finite.
pub fn js_divergence(p: &[f64], q: &[f64]) -> f64 {
    let p_sum: f64 = p.iter().sum();
    let q_sum: f64 = q.iter().sum();
    let m: Vec<f64> = p.iter().zip(q)
        .map(|(&pi, &qi)| 0.5 * (pi / p_sum + qi / q_sum))
        .collect();
    let p_norm: Vec<f64> = p.iter().map(|&pi| pi / p_sum).collect();
    let q_norm: Vec<f64> = q.iter().map(|&qi| qi / q_sum).collect();
    0.5 * kl_divergence(&p_norm, &m) + 0.5 * kl_divergence(&q_norm, &m)
}

/// Total variation distance `TV(P, Q) = ½ Σ |P_i − Q_i|`.
pub fn total_variation(p: &[f64], q: &[f64]) -> f64 {
    assert_eq!(p.len(), q.len());
    let p_sum: f64 = p.iter().sum();
    let q_sum: f64 = q.iter().sum();
    0.5 * p.iter().zip(q).map(|(&pi, &qi)| (pi / p_sum - qi / q_sum).abs()).sum::<f64>()
}

// ── Mutual information ────────────────────────────────────────────────────────

/// Mutual information `I(X;Y) = H(X) + H(Y) − H(X,Y)` from a joint count matrix.
///
/// The matrix has shape `[|X|][|Y|]` where `joint[i][j]` is the number of
/// co-occurrences of event `X=i` and `Y=j`.
pub fn mutual_information_discrete(joint_counts: &[Vec<usize>]) -> f64 {
    let marginal_x: Vec<f64> = joint_counts.iter().map(|row| row.iter().sum::<usize>() as f64).collect();
    let cols = joint_counts[0].len();
    let marginal_y: Vec<f64> = (0..cols).map(|j| joint_counts.iter().map(|row| row[j] as f64).sum()).collect();
    let _total: f64 = marginal_x.iter().sum();

    let h_x = shannon_entropy(&marginal_x);
    let h_y = shannon_entropy(&marginal_y);
    let h_xy = joint_entropy(joint_counts);

    // Numerical stability: MI should be ≥ 0.
    (h_x + h_y - h_xy).max(0.0)
}

/// Normalised mutual information `NMI(X;Y) = I(X;Y) / sqrt(H(X)·H(Y))` ∈ [0, 1].
pub fn normalised_mutual_information(joint_counts: &[Vec<usize>]) -> f64 {
    let marginal_x: Vec<f64> = joint_counts.iter().map(|row| row.iter().sum::<usize>() as f64).collect();
    let cols = joint_counts[0].len();
    let marginal_y: Vec<f64> = (0..cols).map(|j| joint_counts.iter().map(|row| row[j] as f64).sum()).collect();
    let h_x = shannon_entropy(&marginal_x);
    let h_y = shannon_entropy(&marginal_y);
    let denom = (h_x * h_y).sqrt();
    if denom == 0.0 { return 0.0; }
    mutual_information_discrete(joint_counts) / denom
}

// ── Cross-entropy ────────────────────────────────────────────────────────────

/// Cross-entropy `H(P, Q) = -Σ P_i log₂ Q_i`.
///
/// Returns `f64::INFINITY` if `Q_i = 0` at any site where `P_i > 0`.
pub fn cross_entropy(p: &[f64], q: &[f64]) -> f64 {
    assert_eq!(p.len(), q.len());
    let p_sum: f64 = p.iter().sum();
    let q_sum: f64 = q.iter().sum();
    if p_sum == 0.0 { return 0.0; }
    p.iter().zip(q).map(|(&pi, &qi)| {
        let pn = pi / p_sum;
        let qn = qi / q_sum;
        if pn == 0.0 { 0.0 }
        else if qn == 0.0 { f64::INFINITY }
        else { -pn * qn.log2() }
    }).sum()
}

// ── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_uniform_entropy_bits() {
        // Uniform distribution over 8 outcomes → entropy = 3 bits.
        let p = vec![1.0; 8];
        assert!((shannon_entropy(&p) - 3.0).abs() < 1e-10);
    }

    #[test]
    fn test_deterministic_entropy_zero() {
        let p = [1.0, 0.0, 0.0, 0.0];
        assert_eq!(shannon_entropy(&p), 0.0);
    }

    #[test]
    fn test_kl_identical_distributions() {
        let p = [0.5, 0.5];
        assert!(kl_divergence(&p, &p).abs() < 1e-12);
    }

    #[test]
    fn test_kl_divergence_known() {
        // KL([1,0] || [0.5, 0.5]) = 1 bit.
        let p = [1.0, 0.0];
        let q = [0.5, 0.5];
        assert!((kl_divergence(&p, &q) - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_js_divergence_symmetric() {
        let p = [0.7, 0.3];
        let q = [0.2, 0.8];
        let jsd_pq = js_divergence(&p, &q);
        let jsd_qp = js_divergence(&q, &p);
        assert!((jsd_pq - jsd_qp).abs() < 1e-12);
    }

    #[test]
    fn test_js_divergence_bounded() {
        let p = [1.0, 0.0];
        let q = [0.0, 1.0];
        let jsd = js_divergence(&p, &q);
        assert!(jsd <= 1.0 + 1e-12);
        assert!(jsd >= 0.0);
    }

    #[test]
    fn test_mutual_information_independent() {
        // X ⊥ Y → I(X;Y) ≈ 0.
        let joint = vec![
            vec![25, 25],
            vec![25, 25],
        ];
        assert!(mutual_information_discrete(&joint) < 1e-10);
    }

    #[test]
    fn test_mutual_information_perfectly_dependent() {
        // X = Y → I(X;Y) = H(X).
        let joint = vec![
            vec![50, 0],
            vec![0, 50],
        ];
        let mi = mutual_information_discrete(&joint);
        assert!((mi - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_normalised_mi_bounds() {
        let joint = vec![vec![30, 10], vec![5, 55]];
        let nmi = normalised_mutual_information(&joint);
        assert!(nmi >= 0.0);
        assert!(nmi <= 1.0 + 1e-12);
    }

    #[test]
    fn test_cross_entropy_self_equals_entropy() {
        let p = [0.5, 0.25, 0.125, 0.125];
        let h = shannon_entropy(&p);
        let ce = cross_entropy(&p, &p);
        assert!((h - ce).abs() < 1e-12);
    }
}
