#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/math/dim_reduce.hpp
//
// Dimensionality reduction: MDS and t-SNE affinity matrix.
// Header-only — no pybind11 bindings.
//
// Ported from base/src/math/dim_reduce.rs.
// Requires Eigen3.
// ---------------------------------------------------------------------------

#include "math/linalg.hpp"
#include "math/distance.hpp"
#include "math/stats.hpp"

#include <Eigen/Dense>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace base::math {

// ---------------------------------------------------------------------------
// MDS — Classical multidimensional scaling
//
// Input:  distance_matrix (n×n symmetric, zero diagonal)
// Output: embedding (n × n_components)
// ---------------------------------------------------------------------------

inline Matrix mds(const Matrix& dist_mat, int n_components = 2) {
    int n = dist_mat.rows();
    if (dist_mat.cols() != n) throw std::invalid_argument("mds: non-square distance matrix");

    // Double-centering: B = -0.5 * H * D² * H,  H = I - (1/n)11ᵀ
    Eigen::MatrixXd D2(n, n);
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j) {
            double d = dist_mat.get(i, j);
            D2(i, j) = d * d;
        }

    Eigen::MatrixXd H = Eigen::MatrixXd::Identity(n, n)
                      - Eigen::MatrixXd::Ones(n, n) / static_cast<double>(n);
    Eigen::MatrixXd B = -0.5 * H * D2 * H;

    Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> eig(B);
    if (eig.info() != Eigen::Success)
        throw std::runtime_error("mds: eigen decomposition failed");

    // Take the top n_components eigenvalues/vectors (last = largest for SelfAdjoint)
    int total = static_cast<int>(eig.eigenvalues().size());
    Matrix embedding(n, n_components);
    for (int k = 0; k < n_components; ++k) {
        int idx = total - 1 - k;
        double eval = eig.eigenvalues()(idx);
        if (eval <= 0.0) { continue; }  // non-positive eigenvalue → zero coordinate
        double scale = std::sqrt(eval);
        for (int i = 0; i < n; ++i)
            embedding.data(i, k) = eig.eigenvectors()(i, idx) * scale;
    }
    return embedding;
}

// ---------------------------------------------------------------------------
// t-SNE affinity matrix P (symmetric, normalised)
//
// Computes pairwise affinities p_ij = (p_j|i + p_i|j) / (2n) using a
// fixed perplexity via binary search for the per-point Gaussian bandwidth σ_i.
//
// Input:  data (n × d), perplexity (typically 5–50)
// Output: P (n × n symmetric affinity matrix)
// ---------------------------------------------------------------------------

inline Matrix tsne_affinities(const Matrix& data, double perplexity = 30.0) {
    int n = data.rows();
    if (n < 3) throw std::invalid_argument("tsne_affinities: need at least 3 points");

    double log_perp = std::log(perplexity);

    // Pairwise squared distances
    Eigen::MatrixXd D2 = Eigen::MatrixXd::Zero(n, n);
    for (int i = 0; i < n; ++i)
        for (int j = i + 1; j < n; ++j) {
            double d2 = (data.data.row(i) - data.data.row(j)).squaredNorm();
            D2(i, j) = D2(j, i) = d2;
        }

    // Conditional probabilities P(j|i) via binary search on σ_i
    Eigen::MatrixXd P = Eigen::MatrixXd::Zero(n, n);
    const int max_iter = 50;
    const double tol = 1e-5;

    for (int i = 0; i < n; ++i) {
        double beta_lo = -std::numeric_limits<double>::infinity();
        double beta_hi =  std::numeric_limits<double>::infinity();
        double beta = 1.0;

        for (int iter = 0; iter < max_iter; ++iter) {
            // Compute P(j|i) for current beta
            double sum_p = 0.0;
            for (int j = 0; j < n; ++j) {
                if (j == i) { P(i, j) = 0.0; continue; }
                P(i, j) = std::exp(-beta * D2(i, j));
                sum_p += P(i, j);
            }
            if (sum_p < 1e-15) break;

            // Entropy H = log(sum_p) + beta * Σ p_ij * d²_ij / sum_p
            double hdiff = 0.0;
            for (int j = 0; j < n; ++j)
                hdiff += P(i, j) * D2(i, j);
            double H = std::log(sum_p) + beta * hdiff / sum_p;

            // Normalise P(i, ·)
            for (int j = 0; j < n; ++j) P(i, j) /= sum_p;

            double Hdiff = H - log_perp;
            if (std::abs(Hdiff) < tol) break;

            if (Hdiff > 0) { beta_lo = beta; beta = std::isinf(beta_hi) ? beta * 2.0 : (beta + beta_hi) / 2.0; }
            else           { beta_hi = beta; beta = std::isinf(beta_lo) ? beta / 2.0 : (beta + beta_lo) / 2.0; }
        }
    }

    // Symmetrise and normalise: P_ij = (P(j|i) + P(i|j)) / (2n)
    Eigen::MatrixXd Psym = (P + P.transpose()) / (2.0 * static_cast<double>(n));
    Psym = Psym.cwiseMax(1e-12);  // numerical floor

    Matrix result(n, n);
    result.data = Psym;
    return result;
}

} // namespace base::math
