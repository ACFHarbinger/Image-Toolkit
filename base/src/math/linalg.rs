//! Linear algebra primitives for the analytics backbone.
//!
//! Provides a heap-allocated row-major `Matrix<f64>`, vector operations, and
//! PCA via power iteration — the mathematical substrate for dimensionality
//! reduction (Phase 2/10) and software-cartography layout (Phase 1.3).

use std::fmt;

// ── Matrix ──────────────────────────────────────────────────────────────────

/// Row-major, heap-allocated matrix of `f64`.
#[derive(Clone)]
pub struct Matrix {
    rows: usize,
    cols: usize,
    data: Vec<f64>,
}

impl Matrix {
    pub fn new(rows: usize, cols: usize) -> Self {
        Self { rows, cols, data: vec![0.0; rows * cols] }
    }

    pub fn identity(n: usize) -> Self {
        let mut m = Self::new(n, n);
        for i in 0..n {
            m.set(i, i, 1.0);
        }
        m
    }

    pub fn from_rows(rows: &[Vec<f64>]) -> Self {
        assert!(!rows.is_empty());
        let ncols = rows[0].len();
        assert!(rows.iter().all(|r| r.len() == ncols));
        let mut m = Self::new(rows.len(), ncols);
        for (i, row) in rows.iter().enumerate() {
            for (j, &v) in row.iter().enumerate() {
                m.set(i, j, v);
            }
        }
        m
    }

    #[inline] pub fn rows(&self) -> usize { self.rows }
    #[inline] pub fn cols(&self) -> usize { self.cols }
    #[inline] pub fn get(&self, r: usize, c: usize) -> f64 { self.data[r * self.cols + c] }
    #[inline] pub fn set(&mut self, r: usize, c: usize, v: f64) { self.data[r * self.cols + c] = v; }

    pub fn row(&self, r: usize) -> Vec<f64> {
        self.data[r * self.cols..(r + 1) * self.cols].to_vec()
    }

    pub fn col(&self, c: usize) -> Vec<f64> {
        (0..self.rows).map(|r| self.get(r, c)).collect()
    }

    pub fn transpose(&self) -> Self {
        let mut out = Self::new(self.cols, self.rows);
        for r in 0..self.rows {
            for c in 0..self.cols {
                out.set(c, r, self.get(r, c));
            }
        }
        out
    }

    /// Matrix multiply: `self` (m×k) × `rhs` (k×n) → (m×n).
    pub fn mul(&self, rhs: &Self) -> Self {
        assert_eq!(self.cols, rhs.rows, "dimension mismatch: {}×{} · {}×{}", self.rows, self.cols, rhs.rows, rhs.cols);
        let mut out = Self::new(self.rows, rhs.cols);
        for r in 0..self.rows {
            for k in 0..self.cols {
                let a = self.get(r, k);
                if a == 0.0 { continue; }
                for c in 0..rhs.cols {
                    let v = out.get(r, c) + a * rhs.get(k, c);
                    out.set(r, c, v);
                }
            }
        }
        out
    }

    pub fn add(&self, rhs: &Self) -> Self {
        assert_eq!((self.rows, self.cols), (rhs.rows, rhs.cols));
        let data: Vec<f64> = self.data.iter().zip(&rhs.data).map(|(a, b)| a + b).collect();
        Self { rows: self.rows, cols: self.cols, data }
    }

    pub fn scale(&self, s: f64) -> Self {
        let data: Vec<f64> = self.data.iter().map(|&v| v * s).collect();
        Self { rows: self.rows, cols: self.cols, data }
    }

    /// Compute `X^T X` (cross-product / Gram matrix).
    pub fn gram(&self) -> Self {
        self.transpose().mul(self)
    }
}

impl fmt::Debug for Matrix {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Matrix({}×{})", self.rows, self.cols)
    }
}

// ── Vector helpers ───────────────────────────────────────────────────────────

/// Dot product of two equal-length slices.
pub fn dot(a: &[f64], b: &[f64]) -> f64 {
    assert_eq!(a.len(), b.len());
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}

/// Euclidean norm.
pub fn norm(v: &[f64]) -> f64 { dot(v, v).sqrt() }

/// Return a unit vector; panics if the zero vector is passed.
pub fn normalize(v: &[f64]) -> Vec<f64> {
    let n = norm(v);
    assert!(n > 0.0, "cannot normalize the zero vector");
    v.iter().map(|&x| x / n).collect()
}

/// Subtract vector `b` from `a`.
pub fn sub(a: &[f64], b: &[f64]) -> Vec<f64> {
    a.iter().zip(b).map(|(x, y)| x - y).collect()
}

/// Add vectors.
pub fn add_vec(a: &[f64], b: &[f64]) -> Vec<f64> {
    a.iter().zip(b).map(|(x, y)| x + y).collect()
}

/// Scale a vector.
pub fn scale_vec(v: &[f64], s: f64) -> Vec<f64> {
    v.iter().map(|&x| x * s).collect()
}

// ── Gram-Schmidt orthogonalization ───────────────────────────────────────────

/// Orthogonalize `v` against all already-accepted basis vectors `basis`.
pub fn gram_schmidt_step(v: &[f64], basis: &[Vec<f64>]) -> Vec<f64> {
    let mut result = v.to_vec();
    for b in basis {
        let proj = dot(&result, b);
        for (r, &bi) in result.iter_mut().zip(b.iter()) {
            *r -= proj * bi;
        }
    }
    result
}

// ── PCA via power iteration ──────────────────────────────────────────────────

/// Centre the data (subtract column means).
fn center(data: &[Vec<f64>]) -> (Vec<Vec<f64>>, Vec<f64>) {
    let n = data.len();
    let d = data[0].len();
    let means: Vec<f64> = (0..d).map(|j| data.iter().map(|r| r[j]).sum::<f64>() / n as f64).collect();
    let centered: Vec<Vec<f64>> = data.iter().map(|row| row.iter().zip(&means).map(|(x, m)| x - m).collect()).collect();
    (centered, means)
}

/// Multiply the (n×d) data matrix by a d-dimensional vector (compute Xv).
fn mat_vec(data: &[Vec<f64>], v: &[f64]) -> Vec<f64> {
    data.iter().map(|row| dot(row, v)).collect()
}

/// Multiply the transposed data matrix (d×n) by an n-dimensional vector (compute X^T u).
fn mat_t_vec(data: &[Vec<f64>], u: &[f64]) -> Vec<f64> {
    let d = data[0].len();
    (0..d).map(|j| data.iter().zip(u).map(|(row, &ui)| row[j] * ui).sum()).collect()
}

/// Project each centred data point onto the top-`k` principal components.
///
/// Returns an `n × k` matrix (as `Vec<Vec<f64>>`).  Uses randomised power
/// iteration which converges in O(k·n·d·iters) — suitable for the analytics
/// workloads described in Phase 2.3 and Phase 1.3.
pub fn pca_project(data: &[Vec<f64>], k: usize) -> Vec<Vec<f64>> {
    assert!(!data.is_empty());
    let d = data[0].len();
    assert!(k <= d && k > 0);

    let (centered, _means) = center(data);
    let n = centered.len();

    let mut components: Vec<Vec<f64>> = Vec::with_capacity(k);

    // Deflation approach: extract one principal direction at a time.
    let mut residual: Vec<Vec<f64>> = centered.clone();

    for _ in 0..k {
        // Random starting vector.
        let mut v: Vec<f64> = (0..d).map(|i| (i as f64 * 0.7 + 1.0).sin()).collect();
        v = normalize(&v);

        for _ in 0..100 {
            // v ← X^T (X v) / ‖…‖
            let u = mat_vec(&residual, &v);
            let new_v = mat_t_vec(&residual, &u);
            // Orthogonalise against already-found components.
            let ortho = gram_schmidt_step(&new_v, &components);
            let n2 = norm(&ortho);
            if n2 < 1e-12 { break; }
            v = scale_vec(&ortho, 1.0 / n2);
        }

        // Deflate: subtract the outer product rank-1 approximation.
        let scores: Vec<f64> = mat_vec(&residual, &v);
        for (row, &score) in residual.iter_mut().zip(&scores) {
            for (r, &vi) in row.iter_mut().zip(&v) {
                *r -= score * vi;
            }
        }

        components.push(v);
    }

    // Project original centred data onto the extracted components.
    let m = n;
    (0..m).map(|i| {
        components.iter().map(|comp| dot(&centered[i], comp)).collect()
    }).collect()
}

/// Convenience: project down to 2 dimensions.
pub fn pca_2d(data: &[Vec<f64>]) -> Vec<[f64; 2]> {
    let proj = pca_project(data, 2);
    proj.into_iter().map(|v| [v[0], v[1]]).collect()
}

// ── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_matrix_identity_mul() {
        let a = Matrix::from_rows(&[vec![1.0, 2.0], vec![3.0, 4.0]]);
        let i = Matrix::identity(2);
        let r = a.mul(&i);
        assert_eq!(r.get(0, 0), 1.0);
        assert_eq!(r.get(1, 1), 4.0);
    }

    #[test]
    fn test_matrix_transpose() {
        let a = Matrix::from_rows(&[vec![1.0, 2.0, 3.0]]);
        let t = a.transpose();
        assert_eq!(t.rows(), 3);
        assert_eq!(t.cols(), 1);
        assert_eq!(t.get(2, 0), 3.0);
    }

    #[test]
    fn test_dot_and_norm() {
        let a = vec![3.0, 4.0];
        assert_eq!(dot(&a, &a), 25.0);
        assert!((norm(&a) - 5.0).abs() < 1e-10);
    }

    #[test]
    fn test_normalize() {
        let v = vec![0.0, 5.0];
        let u = normalize(&v);
        assert!((norm(&u) - 1.0).abs() < 1e-12);
    }

    #[test]
    fn test_pca_reduces_dimension() {
        let data: Vec<Vec<f64>> = (0..20).map(|i| vec![i as f64, i as f64 * 2.0 + 0.1, i as f64 * 0.5]).collect();
        let proj = pca_project(&data, 2);
        assert_eq!(proj.len(), 20);
        assert_eq!(proj[0].len(), 2);
    }

    #[test]
    fn test_pca_2d() {
        let data: Vec<Vec<f64>> = (0..10).map(|i| vec![i as f64, -(i as f64)]).collect();
        let pts = pca_2d(&data);
        assert_eq!(pts.len(), 10);
    }
}
