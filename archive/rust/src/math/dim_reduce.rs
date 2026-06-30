//! Dimensionality reduction algorithms for the analytics backbone.
//!
//! Provides Classical MDS (Phase 1.3 software cartography), Multidimensional
//! Scaling for SCIP-derived distance matrices, and a t-SNE perplexity
//! pre-processing step.  PCA projection is in `linalg::pca_project`.

use super::linalg::{dot, norm, normalize, sub};

// ── Classical Multidimensional Scaling ────────────────────────────────────────

/// Project points into `k` dimensions via Classical MDS from a symmetric
/// distance matrix.
///
/// Algorithm:
///   1. Double-centre the squared-distance matrix `B = -½ J D² J` where
///      `J = I - (1/n) 11^T` is the centering matrix.
///   2. Extract the top-`k` eigenvectors of `B` via power iteration.
///   3. Return coordinates `Λ^{1/2} V_k`.
///
/// This preserves pairwise Euclidean distances as faithfully as possible in
/// the lower-dimensional embedding — the mathematical core of Phase 1.3.
pub fn mds_project(distance_matrix: &[Vec<f64>], k: usize) -> Vec<Vec<f64>> {
    let n = distance_matrix.len();
    assert!(n >= 2, "need at least 2 points");
    assert!(k >= 1 && k <= n);

    // Step 1: squared distances.
    let d2: Vec<Vec<f64>> = distance_matrix.iter()
        .map(|row| row.iter().map(|&d| d * d).collect())
        .collect();

    // Step 2: double-centring → B.
    let row_means: Vec<f64> = d2.iter().map(|row| row.iter().sum::<f64>() / n as f64).collect();
    let grand_mean: f64 = row_means.iter().sum::<f64>() / n as f64;
    let col_means: Vec<f64> = (0..n).map(|j| d2.iter().map(|row| row[j]).sum::<f64>() / n as f64).collect();

    let mut b = vec![vec![0.0f64; n]; n];
    for i in 0..n {
        for j in 0..n {
            b[i][j] = -0.5 * (d2[i][j] - row_means[i] - col_means[j] + grand_mean);
        }
    }

    // Step 3: top-k eigenvectors of B via deflated power iteration.
    let mut eigenvecs: Vec<Vec<f64>> = Vec::with_capacity(k);
    let mut eigenvals: Vec<f64> = Vec::with_capacity(k);
    let mut residual = b.clone();

    for _ in 0..k {
        let (eigvec, eigval) = power_iteration_sym(&residual, 200, 1e-12);
        if eigval < 0.0 { break; } // MDS embeddings only use positive eigenvalues.

        // Deflate: B ← B − λ v vᵀ
        for i in 0..n {
            for j in 0..n {
                residual[i][j] -= eigval * eigvec[i] * eigvec[j];
            }
        }
        eigenvecs.push(eigvec);
        eigenvals.push(eigval);
    }

    let k_actual = eigenvecs.len();

    // Coordinates: scale eigenvectors by sqrt(eigenvalue).
    let mut coords = vec![vec![0.0f64; k_actual]; n];
    for (dim, (evec, &eval)) in eigenvecs.iter().zip(&eigenvals).enumerate() {
        let scale = eval.sqrt();
        for i in 0..n {
            coords[i][dim] = evec[i] * scale;
        }
    }
    coords
}

/// Power iteration to find the dominant eigenvector/eigenvalue of a symmetric
/// matrix.  Returns `(eigenvector, eigenvalue)`.
fn power_iteration_sym(a: &[Vec<f64>], max_iter: usize, tol: f64) -> (Vec<f64>, f64) {
    let n = a.len();
    // Seeded non-uniform starting vector for deterministic convergence.
    let mut v: Vec<f64> = (0..n).map(|i| (i as f64 + 1.0).recip()).collect();
    v = normalize(&v);

    let mut eigenval = 0.0f64;
    for _ in 0..max_iter {
        let av: Vec<f64> = mat_sym_vec(a, &v);
        let new_eigenval = dot(&v, &av);
        let new_v = normalize(&av);
        let delta = norm(&sub(&new_v, &v));
        v = new_v;
        if (new_eigenval - eigenval).abs() < tol && delta < tol { break; }
        eigenval = new_eigenval;
    }
    // Re-compute final eigenvalue with converged v.
    let av = mat_sym_vec(a, &v);
    eigenval = dot(&v, &av);
    (v, eigenval)
}

fn mat_sym_vec(a: &[Vec<f64>], v: &[f64]) -> Vec<f64> {
    a.iter().map(|row| dot(row, v)).collect()
}

// ── Isomap skeleton (geodesic distances via Dijkstra) ────────────────────────

/// Compute shortest-path (geodesic) distance matrix via Dijkstra's algorithm.
///
/// Input: adjacency weight matrix (0 means no edge, positive = edge weight).
/// Returns the all-pairs shortest-path matrix for use in Isomap (Phase 1.3).
pub fn geodesic_distances(weights: &[Vec<f64>]) -> Vec<Vec<f64>> {
    let n = weights.len();
    let mut dist = vec![vec![f64::INFINITY; n]; n];
    for i in 0..n { dist[i][i] = 0.0; }

    for src in 0..n {
        // Simple O(n²) Dijkstra — sufficient for the AST graph sizes in Phase 1.
        let mut visited = vec![false; n];
        dist[src][src] = 0.0;
        for _ in 0..n {
            // Find unvisited node with minimum tentative distance.
            let u = (0..n).filter(|&v| !visited[v])
                .min_by(|&a, &b| dist[src][a].partial_cmp(&dist[src][b]).unwrap())
                .unwrap();
            visited[u] = true;
            for v in 0..n {
                let w = weights[u][v];
                if w > 0.0 {
                    let d = dist[src][u] + w;
                    if d < dist[src][v] { dist[src][v] = d; }
                }
            }
        }
    }
    dist
}

// ── t-SNE helpers ─────────────────────────────────────────────────────────────

/// Compute the perplexity-calibrated Gaussian affinities `P_{j|i}` for t-SNE.
///
/// For each point `i`, binary-searches for the bandwidth `σ_i` that yields
/// the requested perplexity `Perp = 2^{H(P_i)}` where `H(P_i)` is the
/// Shannon entropy of the conditional distribution.
///
/// Returns the n×n matrix of (asymmetric) conditional probabilities; callers
/// should symmetrise with `P = (P + Pᵀ) / (2n)` before the gradient loop.
pub fn tsne_affinities(distances_sq: &[Vec<f64>], perplexity: f64) -> Vec<Vec<f64>> {
    assert!(perplexity > 0.0);
    let n = distances_sq.len();
    let log_perp = perplexity.ln();
    let mut p = vec![vec![0.0f64; n]; n];

    for i in 0..n {
        // Binary search for σ_i (stored as 2σ²).
        let mut beta_lo = f64::NEG_INFINITY;
        let mut beta_hi = f64::INFINITY;
        let mut beta = 1.0f64;

        for _ in 0..50 {
            // Compute P_{j|i} and entropy H.
            let mut sum = 0.0f64;
            for j in 0..n {
                if i != j {
                    p[i][j] = (-distances_sq[i][j] * beta).exp();
                    sum += p[i][j];
                }
            }
            if sum == 0.0 { break; }
            let mut h = 0.0f64;
            for j in 0..n {
                if i != j {
                    p[i][j] /= sum;
                    if p[i][j] > 1e-12 { h -= p[i][j] * p[i][j].ln(); }
                }
            }
            let diff = h - log_perp;
            if diff.abs() < 1e-5 { break; }
            if diff > 0.0 {
                beta_lo = beta;
                beta = if beta_hi.is_infinite() { beta * 2.0 } else { (beta + beta_hi) / 2.0 };
            } else {
                beta_hi = beta;
                beta = if beta_lo.is_infinite() { beta / 2.0 } else { (beta + beta_lo) / 2.0 };
            }
        }
    }
    p
}

// ── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use super::super::distance::euclidean;

    fn square_4pts() -> Vec<Vec<f64>> {
        vec![
            vec![0.0, 0.0],
            vec![1.0, 0.0],
            vec![1.0, 1.0],
            vec![0.0, 1.0],
        ]
    }

    fn dist_matrix(pts: &[Vec<f64>]) -> Vec<Vec<f64>> {
        let n = pts.len();
        let mut m = vec![vec![0.0; n]; n];
        for i in 0..n {
            for j in 0..n {
                m[i][j] = euclidean(&pts[i], &pts[j]);
            }
        }
        m
    }

    #[test]
    fn test_mds_recovers_2d_square() {
        let pts = square_4pts();
        let dm = dist_matrix(&pts);
        let emb = mds_project(&dm, 2);
        assert_eq!(emb.len(), 4);
        assert_eq!(emb[0].len(), 2);

        // Pairwise distances in the embedding should match the input distances.
        for i in 0..4 {
            for j in 0..4 {
                let d_orig = dm[i][j];
                let d_emb = euclidean(&emb[i], &emb[j]);
                assert!((d_orig - d_emb).abs() < 1e-4,
                    "distance mismatch ({i},{j}): orig={d_orig:.4} emb={d_emb:.4}");
            }
        }
    }

    #[test]
    fn test_mds_single_dim() {
        let pts: Vec<Vec<f64>> = (0..5).map(|i| vec![i as f64]).collect();
        let dm = dist_matrix(&pts);
        let emb = mds_project(&dm, 1);
        assert_eq!(emb.len(), 5);
    }

    #[test]
    fn test_geodesic_diagonal_zero() {
        let w = vec![
            vec![0.0, 1.0, 0.0],
            vec![1.0, 0.0, 2.0],
            vec![0.0, 2.0, 0.0],
        ];
        let d = geodesic_distances(&w);
        assert_eq!(d[0][0], 0.0);
        assert!((d[0][2] - 3.0).abs() < 1e-10); // 0→1→2
    }

    #[test]
    fn test_tsne_affinities_row_sum_one() {
        let pts: Vec<Vec<f64>> = (0..8).map(|i| vec![i as f64]).collect();
        let n = pts.len();
        let dsq: Vec<Vec<f64>> = (0..n).map(|i| (0..n).map(|j| {
            let d = pts[i][0] - pts[j][0];
            d * d
        }).collect()).collect();
        let p = tsne_affinities(&dsq, 3.0);
        for (i, row) in p.iter().enumerate() {
            let sum: f64 = row.iter().sum();
            assert!((sum - 1.0).abs() < 1e-6, "row {i} sums to {sum}");
        }
    }
}
