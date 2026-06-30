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
#include <limits>
#include <numeric>
#include <stdexcept>
#include <utility>
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

/// Sample variance (ddof=1 denominator). Returns 0 for fewer than 2 elements.
inline double sample_variance(const std::vector<double>& xs) { return variance(xs, 1); }

/// Sample standard deviation (ddof=1). Returns 0 for fewer than 2 elements.
inline double sample_std_dev(const std::vector<double>& xs) { return std_dev(xs, 1); }

/// Population covariance of two equal-length series.
inline double covariance(const std::vector<double>& xs, const std::vector<double>& ys) {
    if (xs.size() != ys.size()) throw std::invalid_argument("covariance: size mismatch");
    if (xs.empty()) return 0.0;
    double mx = mean(xs), my = mean(ys), cov = 0.0;
    for (std::size_t i = 0; i < xs.size(); ++i) cov += (xs[i] - mx) * (ys[i] - my);
    return cov / static_cast<double>(xs.size());
}

/// Minimum value. Returns +∞ for empty input.
inline double min_val(const std::vector<double>& xs) {
    return xs.empty() ? std::numeric_limits<double>::infinity()
                      : *std::min_element(xs.begin(), xs.end());
}

/// Maximum value. Returns -∞ for empty input.
inline double max_val(const std::vector<double>& xs) {
    return xs.empty() ? -std::numeric_limits<double>::infinity()
                      : *std::max_element(xs.begin(), xs.end());
}

/// Nearest-rank percentile. p ∈ [0, 1]. Returns NaN for empty input.
inline double percentile(const std::vector<double>& xs, double p) {
    if (xs.empty()) return std::numeric_limits<double>::quiet_NaN();
    std::vector<double> s(xs);
    std::sort(s.begin(), s.end());
    std::size_t idx = static_cast<std::size_t>(
        std::round(p * static_cast<double>(s.size() - 1)));
    return s[std::min(idx, s.size() - 1)];
}

/// Interquartile range Q3 − Q1 (nearest-rank percentile).
inline double iqr(const std::vector<double>& xs) {
    return percentile(xs, 0.75) - percentile(xs, 0.25);
}

/// Equal-width histogram. Returns (bin_edges [size bins+1], counts [size bins]).
inline std::pair<std::vector<double>, std::vector<std::size_t>>
histogram(const std::vector<double>& xs, std::size_t bins) {
    if (bins == 0) throw std::invalid_argument("histogram: bins must be > 0");
    double lo = min_val(xs), hi = max_val(xs), range = hi - lo;
    std::vector<std::size_t> counts(bins, 0);
    std::vector<double> edges(bins + 1);
    for (std::size_t i = 0; i <= bins; ++i)
        edges[i] = lo + range * static_cast<double>(i) / static_cast<double>(bins);
    for (double x : xs) {
        std::size_t bin = range == 0.0 ? 0
            : static_cast<std::size_t>((x - lo) / range * static_cast<double>(bins));
        counts[std::min(bin, bins - 1)]++;
    }
    return {edges, counts};
}

/// Convert raw counts to normalised probabilities summing to 1.
inline std::vector<double> counts_to_probs(const std::vector<std::size_t>& counts) {
    std::size_t total = 0;
    for (auto c : counts) total += c;
    std::vector<double> probs(counts.size(), 0.0);
    if (total == 0) return probs;
    for (std::size_t i = 0; i < counts.size(); ++i)
        probs[i] = static_cast<double>(counts[i]) / static_cast<double>(total);
    return probs;
}

/// Population covariance matrix for n×d data. Returns d×d flat row-major vector.
inline std::vector<double> covariance_matrix(const std::vector<std::vector<double>>& data) {
    if (data.empty()) return {};
    std::size_t n = data.size(), d = data[0].size();
    std::vector<double> means(d, 0.0);
    for (const auto& row : data)
        for (std::size_t j = 0; j < d; ++j) means[j] += row[j];
    for (auto& m : means) m /= static_cast<double>(n);
    std::vector<double> cov(d * d, 0.0);
    for (const auto& row : data)
        for (std::size_t j = 0; j < d; ++j)
            for (std::size_t k = 0; k < d; ++k)
                cov[j * d + k] += (row[j] - means[j]) * (row[k] - means[k]);
    for (auto& v : cov) v /= static_cast<double>(n);
    return cov;
}

} // namespace base::math
