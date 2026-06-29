#pragma once
// ---------------------------------------------------------------------------
// batch/include/batch/math/stats.hpp
//
// Descriptive statistics.
// Header-only — no pybind11 bindings.
//
// Ported from base/src/math/stats.rs.
// ---------------------------------------------------------------------------

#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>
#include <vector>

namespace base::math {

inline double mean(const std::vector<double>& xs) {
    if (xs.empty()) throw std::invalid_argument("mean: empty vector");
    return std::accumulate(xs.begin(), xs.end(), 0.0) / static_cast<double>(xs.size());
}

/// Median (modifies a copy — O(n log n)).
inline double median(std::vector<double> xs) {
    if (xs.empty()) throw std::invalid_argument("median: empty vector");
    std::sort(xs.begin(), xs.end());
    std::size_t n = xs.size();
    return (n % 2 == 0) ? (xs[n / 2 - 1] + xs[n / 2]) / 2.0 : xs[n / 2];
}

/// Population standard deviation (ddof = 0).
inline double std_dev(const std::vector<double>& xs, int ddof = 0) {
    if (xs.size() <= static_cast<std::size_t>(ddof))
        throw std::invalid_argument("std_dev: not enough elements");
    double m = mean(xs);
    double var = 0.0;
    for (double x : xs) var += (x - m) * (x - m);
    return std::sqrt(var / static_cast<double>(xs.size() - ddof));
}

/// Variance (ddof = 0 for population, 1 for sample).
inline double variance(const std::vector<double>& xs, int ddof = 0) {
    double s = std_dev(xs, ddof);
    return s * s;
}

/// Pearson correlation coefficient in [−1, 1].
inline double pearson(const std::vector<double>& a, const std::vector<double>& b) {
    if (a.size() != b.size()) throw std::invalid_argument("pearson: size mismatch");
    if (a.size() < 2) throw std::invalid_argument("pearson: need at least 2 elements");
    double ma = mean(a), mb = mean(b);
    double num = 0.0, da2 = 0.0, db2 = 0.0;
    for (std::size_t i = 0; i < a.size(); ++i) {
        double da = a[i] - ma, db = b[i] - mb;
        num += da * db; da2 += da * da; db2 += db * db;
    }
    double denom = std::sqrt(da2 * db2);
    return denom < 1e-15 ? 0.0 : num / denom;
}

/// Z-score normalisation — returns (x − mean) / std_dev for each element.
inline std::vector<double> z_score(const std::vector<double>& xs) {
    double m = mean(xs);
    double s = std_dev(xs, 1);  // sample std dev
    std::vector<double> out(xs.size());
    for (std::size_t i = 0; i < xs.size(); ++i)
        out[i] = s < 1e-15 ? 0.0 : (xs[i] - m) / s;
    return out;
}

/// Min–max normalisation to [0, 1].
inline std::vector<double> min_max_normalize(const std::vector<double>& xs) {
    auto [lo, hi] = std::minmax_element(xs.begin(), xs.end());
    double range = *hi - *lo;
    std::vector<double> out(xs.size());
    for (std::size_t i = 0; i < xs.size(); ++i)
        out[i] = range < 1e-15 ? 0.0 : (xs[i] - *lo) / range;
    return out;
}

} // namespace base::math
