#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/math/linalg.hpp
//
// Row-major Matrix<double> and PCA via Eigen3.
// Header-only — no pybind11 bindings.
//
// Ported from base/src/math/linalg.rs.
// Requires Eigen3 (already a CMake dependency of batch/).
// ---------------------------------------------------------------------------

#include <Eigen/Dense>

#include <cassert>
#include <stdexcept>
#include <vector>

namespace base::math {

// ---------------------------------------------------------------------------
// Matrix — thin row-major wrapper around Eigen::MatrixXd
// ---------------------------------------------------------------------------

class Matrix {
public:
    Eigen::MatrixXd data;

    Matrix() = default;
    Matrix(int rows, int cols) : data(Eigen::MatrixXd::Zero(rows, cols)) {}

    static Matrix identity(int n) {
        Matrix m(n, n);
        m.data = Eigen::MatrixXd::Identity(n, n);
        return m;
    }

    static Matrix from_rows(const std::vector<std::vector<double>>& rows) {
        if (rows.empty()) throw std::invalid_argument("Matrix::from_rows: empty input");
        int ncols = static_cast<int>(rows[0].size());
        Matrix m(static_cast<int>(rows.size()), ncols);
        for (int i = 0; i < static_cast<int>(rows.size()); ++i) {
            assert(static_cast<int>(rows[i].size()) == ncols);
            for (int j = 0; j < ncols; ++j) m.data(i, j) = rows[i][j];
        }
        return m;
    }

    int rows() const { return static_cast<int>(data.rows()); }
    int cols() const { return static_cast<int>(data.cols()); }

    double  get(int r, int c) const { return data(r, c); }
    void    set(int r, int c, double v) { data(r, c) = v; }

    std::vector<double> row(int r) const {
        std::vector<double> v(cols());
        for (int j = 0; j < cols(); ++j) v[j] = data(r, j);
        return v;
    }

    Matrix transpose() const { Matrix m; m.data = data.transpose(); return m; }

    Matrix mul(const Matrix& rhs) const {
        if (cols() != rhs.rows())
            throw std::invalid_argument("Matrix::mul: dimension mismatch");
        Matrix m; m.data = data * rhs.data; return m;
    }

    Matrix add(const Matrix& rhs) const { Matrix m; m.data = data + rhs.data; return m; }
    Matrix sub(const Matrix& rhs) const { Matrix m; m.data = data - rhs.data; return m; }
    Matrix scale(double s)        const { Matrix m; m.data = data * s; return m; }
};

// ---------------------------------------------------------------------------
// PCA — returns (scores, components, explained_variance_ratio)
// scores: (n_samples, n_components)  — projection of input onto components
// components: (n_components, n_features) — principal axes
// ---------------------------------------------------------------------------

struct PCAResult {
    Matrix scores;
    Matrix components;
    std::vector<double> explained_variance_ratio;
};

/// Fit PCA on data (n_samples × n_features) and project to n_components dims.
inline PCAResult pca(const Matrix& data, int n_components) {
    if (n_components <= 0 || n_components > data.cols())
        throw std::invalid_argument("pca: invalid n_components");
    int n = data.rows(), d = data.cols();

    // Centre
    Eigen::VectorXd mu = data.data.colwise().mean();
    Eigen::MatrixXd centred = data.data.rowwise() - mu.transpose();

    // Covariance matrix (sample)
    Eigen::MatrixXd cov = (centred.transpose() * centred) / static_cast<double>(n - 1);

    // Eigen decomposition (symmetric)
    Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> eig(cov);
    if (eig.info() != Eigen::Success)
        throw std::runtime_error("pca: eigen decomposition failed");

    // Eigen returns eigenvalues in ascending order — reverse for descending
    int total = static_cast<int>(eig.eigenvalues().size());
    double total_var = eig.eigenvalues().sum();

    PCAResult result;
    result.components = Matrix(n_components, d);
    result.explained_variance_ratio.resize(n_components);

    for (int k = 0; k < n_components; ++k) {
        int idx = total - 1 - k;
        Eigen::VectorXd ev = eig.eigenvectors().col(idx);
        for (int j = 0; j < d; ++j) result.components.data(k, j) = ev(j);
        result.explained_variance_ratio[k] =
            total_var > 0 ? eig.eigenvalues()(idx) / total_var : 0.0;
    }

    // Project
    Eigen::MatrixXd comp = result.components.data;  // (n_components, d)
    Eigen::MatrixXd proj = centred * comp.transpose();  // (n, n_components)
    result.scores = Matrix(n, n_components);
    result.scores.data = proj;

    return result;
}

} // namespace base::math
