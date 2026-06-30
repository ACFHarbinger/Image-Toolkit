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
#include <limits>
#include <stdexcept>
#include <vector>

namespace base::math {

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

/// Entropy in nats (natural log base) = shannon_entropy / log2(e).
inline double entropy_nats(const std::vector<double>& p) {
    return shannon_entropy(p) / std::log2(std::exp(1.0));
}

/// Shannon entropy computed from raw integer counts (normalises internally).
inline double empirical_entropy(const std::vector<std::size_t>& counts) {
    std::vector<double> probs(counts.size());
    for (std::size_t i = 0; i < counts.size(); ++i) probs[i] = static_cast<double>(counts[i]);
    return shannon_entropy(probs);
}

/// Joint entropy H(X,Y) from a 2-D count matrix (rows = X values, cols = Y).
inline double joint_entropy(const std::vector<std::vector<std::size_t>>& joint_counts) {
    std::vector<double> flat;
    for (const auto& row : joint_counts)
        for (std::size_t c : row) flat.push_back(static_cast<double>(c));
    return shannon_entropy(flat);
}

/// Conditional entropy H(Y|X) = H(X,Y) − H(X) from a joint count matrix.
inline double conditional_entropy(const std::vector<std::vector<std::size_t>>& joint_counts) {
    std::vector<double> marginal_x;
    for (const auto& row : joint_counts) {
        double sum = 0.0;
        for (std::size_t c : row) sum += static_cast<double>(c);
        marginal_x.push_back(sum);
    }
    return joint_entropy(joint_counts) - shannon_entropy(marginal_x);
}

/// Total variation distance TV(P,Q) = ½ Σ |P_i − Q_i|. Normalises inputs internally.
inline double total_variation(const std::vector<double>& p, const std::vector<double>& q) {
    if (p.size() != q.size()) throw std::invalid_argument("total_variation: size mismatch");
    double p_sum = 0.0, q_sum = 0.0;
    for (double x : p) p_sum += x;
    for (double x : q) q_sum += x;
    double tv = 0.0;
    for (std::size_t i = 0; i < p.size(); ++i)
        tv += std::abs(p[i] / p_sum - q[i] / q_sum);
    return 0.5 * tv;
}

/// Mutual information I(X;Y)=H(X)+H(Y)−H(X,Y) from a joint count matrix.
/// Returns max(result, 0) for numerical stability.
inline double mutual_information_discrete(
    const std::vector<std::vector<std::size_t>>& joint_counts)
{
    if (joint_counts.empty()) return 0.0;
    std::vector<double> marginal_x;
    for (const auto& row : joint_counts) {
        double sum = 0.0;
        for (std::size_t c : row) sum += static_cast<double>(c);
        marginal_x.push_back(sum);
    }
    std::size_t cols = joint_counts[0].size();
    std::vector<double> marginal_y(cols, 0.0);
    for (const auto& row : joint_counts)
        for (std::size_t j = 0; j < cols; ++j)
            marginal_y[j] += static_cast<double>(row[j]);
    double mi = shannon_entropy(marginal_x) + shannon_entropy(marginal_y)
                - joint_entropy(joint_counts);
    return mi > 0.0 ? mi : 0.0;
}

/// Normalised mutual information NMI(X;Y)=I(X;Y)/sqrt(H(X)·H(Y)) ∈ [0,1].
inline double normalised_mutual_information(
    const std::vector<std::vector<std::size_t>>& joint_counts)
{
    if (joint_counts.empty()) return 0.0;
    std::vector<double> marginal_x;
    for (const auto& row : joint_counts) {
        double sum = 0.0;
        for (std::size_t c : row) sum += static_cast<double>(c);
        marginal_x.push_back(sum);
    }
    std::size_t cols = joint_counts[0].size();
    std::vector<double> marginal_y(cols, 0.0);
    for (const auto& row : joint_counts)
        for (std::size_t j = 0; j < cols; ++j)
            marginal_y[j] += static_cast<double>(row[j]);
    double denom = std::sqrt(shannon_entropy(marginal_x) * shannon_entropy(marginal_y));
    if (denom == 0.0) return 0.0;
    return mutual_information_discrete(joint_counts) / denom;
}

/// Cross-entropy H(P,Q) = -Σ P_i log₂ Q_i. Returns +∞ if Q_i=0 where P_i>0.
inline double cross_entropy(const std::vector<double>& p, const std::vector<double>& q) {
    if (p.size() != q.size()) throw std::invalid_argument("cross_entropy: size mismatch");
    double p_sum = 0.0, q_sum = 0.0;
    for (double x : p) p_sum += x;
    for (double x : q) q_sum += x;
    if (p_sum == 0.0) return 0.0;
    double ce = 0.0;
    for (std::size_t i = 0; i < p.size(); ++i) {
        double pn = p[i] / p_sum;
        double qn = q[i] / q_sum;
        if (pn == 0.0) continue;
        if (qn == 0.0) return std::numeric_limits<double>::infinity();
        ce -= pn * std::log2(qn);
    }
    return ce;
}

} // namespace base::math
