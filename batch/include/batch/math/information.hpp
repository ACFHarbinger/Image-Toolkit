#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/math/information.hpp
//
// Information-theoretic measures.
// Header-only — no pybind11 bindings.
//
// Ported from base/src/math/information.rs.
// ---------------------------------------------------------------------------

#include <cmath>
#include <stdexcept>
#include <vector>

namespace batch::math {

/// Shannon entropy H(p) = -Σ p_i log2(p_i).
/// p must be a probability distribution (non-negative, sums to 1).
inline double shannon_entropy(const std::vector<double>& p) {
    double h = 0.0;
    for (double pi : p) if (pi > 0.0) h -= pi * std::log2(pi);
    return h;
}

/// KL divergence D_KL(p || q) = Σ p_i log(p_i / q_i).
/// Returns +inf where q_i = 0 and p_i > 0.
inline double kl_divergence(const std::vector<double>& p, const std::vector<double>& q) {
    if (p.size() != q.size()) throw std::invalid_argument("kl_divergence: size mismatch");
    double kl = 0.0;
    for (std::size_t i = 0; i < p.size(); ++i) {
        if (p[i] <= 0.0) continue;
        if (q[i] <= 0.0) return std::numeric_limits<double>::infinity();
        kl += p[i] * std::log(p[i] / q[i]);
    }
    return kl;
}

/// Jensen–Shannon divergence (symmetric, bounded in [0, ln 2]).
inline double js_divergence(const std::vector<double>& p, const std::vector<double>& q) {
    if (p.size() != q.size()) throw std::invalid_argument("js_divergence: size mismatch");
    std::vector<double> m(p.size());
    for (std::size_t i = 0; i < p.size(); ++i) m[i] = (p[i] + q[i]) / 2.0;
    return (kl_divergence(p, m) + kl_divergence(q, m)) / 2.0;
}

/// Jensen–Shannon distance = sqrt(JSD).
inline double js_distance(const std::vector<double>& p, const std::vector<double>& q) {
    return std::sqrt(js_divergence(p, q));
}

/// Mutual information I(X;Y) estimated from a joint probability matrix.
/// joint[i][j] = P(X=i, Y=j).
inline double mutual_information(const std::vector<std::vector<double>>& joint) {
    if (joint.empty()) throw std::invalid_argument("mutual_information: empty matrix");
    std::size_t rows = joint.size(), cols = joint[0].size();
    std::vector<double> px(rows, 0.0), py(cols, 0.0);
    for (std::size_t i = 0; i < rows; ++i)
        for (std::size_t j = 0; j < cols; ++j) {
            px[i] += joint[i][j];
            py[j] += joint[i][j];
        }
    double mi = 0.0;
    for (std::size_t i = 0; i < rows; ++i)
        for (std::size_t j = 0; j < cols; ++j) {
            double pij = joint[i][j];
            if (pij <= 0.0 || px[i] <= 0.0 || py[j] <= 0.0) continue;
            mi += pij * std::log(pij / (px[i] * py[j]));
        }
    return mi;
}

} // namespace batch::math
