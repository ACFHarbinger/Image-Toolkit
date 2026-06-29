#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/math/distance.hpp
//
// Distance and similarity metrics.
// Header-only — no pybind11 bindings.
//
// Ported from base/src/math/distance.rs.
// ---------------------------------------------------------------------------

#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>
#include <vector>

namespace base::math {

/// Euclidean distance between two equal-length vectors.
inline double euclidean(const std::vector<double>& a, const std::vector<double>& b) {
    if (a.size() != b.size()) throw std::invalid_argument("euclidean: size mismatch");
    double sum = 0.0;
    for (std::size_t i = 0; i < a.size(); ++i) { double d = a[i] - b[i]; sum += d * d; }
    return std::sqrt(sum);
}

/// Squared Euclidean distance (avoids sqrt — useful when only ordering matters).
inline double euclidean_sq(const std::vector<double>& a, const std::vector<double>& b) {
    if (a.size() != b.size()) throw std::invalid_argument("euclidean_sq: size mismatch");
    double sum = 0.0;
    for (std::size_t i = 0; i < a.size(); ++i) { double d = a[i] - b[i]; sum += d * d; }
    return sum;
}

/// Cosine similarity in [−1, 1].  Returns 0 for zero vectors.
inline double cosine_similarity(const std::vector<double>& a, const std::vector<double>& b) {
    if (a.size() != b.size()) throw std::invalid_argument("cosine_similarity: size mismatch");
    double dot = 0.0, na = 0.0, nb = 0.0;
    for (std::size_t i = 0; i < a.size(); ++i) {
        dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i];
    }
    if (na == 0.0 || nb == 0.0) return 0.0;
    return dot / (std::sqrt(na) * std::sqrt(nb));
}

/// Cosine distance = 1 − cosine_similarity.
inline double cosine_distance(const std::vector<double>& a, const std::vector<double>& b) {
    return 1.0 - cosine_similarity(a, b);
}

/// Hamming distance: number of positions where a[i] != b[i].
inline std::size_t hamming(const std::vector<bool>& a, const std::vector<bool>& b) {
    if (a.size() != b.size()) throw std::invalid_argument("hamming: size mismatch");
    std::size_t dist = 0;
    for (std::size_t i = 0; i < a.size(); ++i) if (a[i] != b[i]) ++dist;
    return dist;
}

/// Bhattacharyya distance between two probability distributions.
/// Both vectors must be non-negative and sum to 1.
inline double bhattacharyya(const std::vector<double>& p, const std::vector<double>& q) {
    if (p.size() != q.size()) throw std::invalid_argument("bhattacharyya: size mismatch");
    double bc = 0.0;
    for (std::size_t i = 0; i < p.size(); ++i) bc += std::sqrt(p[i] * q[i]);
    bc = std::clamp(bc, 0.0, 1.0);
    return -std::log(bc + 1e-15);
}

/// Hellinger distance in [0, 1].
inline double hellinger(const std::vector<double>& p, const std::vector<double>& q) {
    if (p.size() != q.size()) throw std::invalid_argument("hellinger: size mismatch");
    double sum = 0.0;
    for (std::size_t i = 0; i < p.size(); ++i) {
        double d = std::sqrt(p[i]) - std::sqrt(q[i]);
        sum += d * d;
    }
    return std::sqrt(sum) / std::sqrt(2.0);
}

/// Manhattan (L1) distance.
inline double manhattan(const std::vector<double>& a, const std::vector<double>& b) {
    if (a.size() != b.size()) throw std::invalid_argument("manhattan: size mismatch");
    double sum = 0.0;
    for (std::size_t i = 0; i < a.size(); ++i) sum += std::abs(a[i] - b[i]);
    return sum;
}

} // namespace base::math
