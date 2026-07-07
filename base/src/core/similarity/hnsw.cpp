// ---------------------------------------------------------------------------
// base/src/core/similarity/hnsw.cpp
// Hierarchical Navigable Small World index for embedding vectors.
// Vectors are L2-normalised on insert, so squared-L2 distance is monotone
// with cosine similarity: d = 2 - 2*cos  ⇒  cos = 1 - d/2.
// ---------------------------------------------------------------------------
#include "core/similarity.hpp"

#include <algorithm>
#include <cmath>
#include <queue>
#include <unordered_set>

namespace base::similarity {

HnswIndex::HnswIndex(int dim, int M, int ef_construction, uint64_t seed)
    : dim_(dim),
      M_(std::max(2, M)),
      max_M0_(2 * std::max(2, M)),
      ef_construction_(std::max(ef_construction, M)),
      level_mult_(1.0 / std::log(static_cast<double>(std::max(2, M)))),
      rng_state_(seed ? seed : 88172645463325252ULL) {}

float HnswIndex::dist(const float* a, const float* b) const {
    float d = 0.f;
    for (int i = 0; i < dim_; ++i) {
        float t = a[i] - b[i];
        d += t * t;
    }
    return d;
}

int HnswIndex::random_level() {
    // xorshift64
    rng_state_ ^= rng_state_ << 13;
    rng_state_ ^= rng_state_ >> 7;
    rng_state_ ^= rng_state_ << 17;
    double u = (rng_state_ >> 11) * (1.0 / 9007199254740992.0);  // [0, 1)
    u = std::max(u, 1e-12);
    return static_cast<int>(-std::log(u) * level_mult_);
}

// Best-first search on one layer. `results` returns (distance, id) sorted asc.
void HnswIndex::search_layer(const float* q, int entry, int layer, int ef,
                             std::vector<std::pair<float, int>>& results) const {
    std::unordered_set<int> visited{entry};
    // min-heap of candidates, max-heap of current best `ef`
    std::priority_queue<std::pair<float, int>, std::vector<std::pair<float, int>>,
                        std::greater<>> candidates;
    std::priority_queue<std::pair<float, int>> best;

    float d0 = dist(q, vec(entry));
    candidates.emplace(d0, entry);
    best.emplace(d0, entry);

    while (!candidates.empty()) {
        auto [dc, c] = candidates.top();
        if (dc > best.top().first && static_cast<int>(best.size()) >= ef) break;
        candidates.pop();

        for (int nb : links_[c][layer]) {
            if (!visited.insert(nb).second) continue;
            float d = dist(q, vec(nb));
            if (static_cast<int>(best.size()) < ef || d < best.top().first) {
                candidates.emplace(d, nb);
                best.emplace(d, nb);
                if (static_cast<int>(best.size()) > ef) best.pop();
            }
        }
    }

    results.clear();
    results.reserve(best.size());
    while (!best.empty()) {
        results.push_back(best.top());
        best.pop();
    }
    std::sort(results.begin(), results.end());
}

// Simple closest-first neighbour selection (keeps at most M).
std::vector<int> HnswIndex::select_neighbors(const float* /*q*/,
                                             std::vector<std::pair<float, int>>& cand,
                                             int M) const {
    std::sort(cand.begin(), cand.end());
    std::vector<int> out;
    out.reserve(std::min<size_t>(M, cand.size()));
    for (const auto& [d, id] : cand) {
        out.push_back(id);
        if (static_cast<int>(out.size()) >= M) break;
    }
    return out;
}

void HnswIndex::add(const std::vector<float>& raw) {
    // Normalise
    std::vector<float> v(raw.begin(), raw.begin() + std::min<size_t>(raw.size(), dim_));
    v.resize(dim_, 0.f);
    float norm = 0.f;
    for (float x : v) norm += x * x;
    norm = std::sqrt(std::max(norm, 1e-12f));
    for (float& x : v) x /= norm;

    int id = static_cast<int>(data_.size());
    int level = random_level();

    data_.push_back(std::move(v));
    levels_.push_back(level);
    links_.emplace_back(level + 1);

    if (entry_point_ < 0) {
        entry_point_ = id;
        max_level_ = level;
        return;
    }

    const float* q = vec(id);
    int ep = entry_point_;

    // Greedy descent through layers above the new node's level
    for (int layer = max_level_; layer > level; --layer) {
        bool improved = true;
        float d_ep = dist(q, vec(ep));
        while (improved) {
            improved = false;
            for (int nb : links_[ep][layer]) {
                float d = dist(q, vec(nb));
                if (d < d_ep) {
                    d_ep = d;
                    ep = nb;
                    improved = true;
                }
            }
        }
    }

    // Insert on layers min(level, max_level_) .. 0
    for (int layer = std::min(level, max_level_); layer >= 0; --layer) {
        std::vector<std::pair<float, int>> cand;
        search_layer(q, ep, layer, ef_construction_, cand);
        int Mmax = (layer == 0) ? max_M0_ : M_;
        std::vector<int> neighbors = select_neighbors(q, cand, M_);

        links_[id][layer] = neighbors;
        for (int nb : neighbors) {
            auto& nb_links = links_[nb][layer];
            nb_links.push_back(id);
            if (static_cast<int>(nb_links.size()) > Mmax) {
                // Prune to the Mmax closest of nb
                std::vector<std::pair<float, int>> pruned;
                pruned.reserve(nb_links.size());
                for (int x : nb_links) pruned.emplace_back(dist(vec(nb), vec(x)), x);
                nb_links = select_neighbors(vec(nb), pruned, Mmax);
            }
        }
        if (!cand.empty()) ep = cand.front().second;
    }

    if (level > max_level_) {
        max_level_ = level;
        entry_point_ = id;
    }
}

std::vector<std::pair<size_t, float>> HnswIndex::knn(const std::vector<float>& query,
                                                     int k, int ef_search) const {
    std::vector<std::pair<size_t, float>> out;
    if (entry_point_ < 0) return out;

    std::vector<float> q(query.begin(), query.begin() + std::min<size_t>(query.size(), dim_));
    q.resize(dim_, 0.f);
    float norm = 0.f;
    for (float x : q) norm += x * x;
    norm = std::sqrt(std::max(norm, 1e-12f));
    for (float& x : q) x /= norm;

    int ep = entry_point_;
    for (int layer = max_level_; layer > 0; --layer) {
        bool improved = true;
        float d_ep = dist(q.data(), vec(ep));
        while (improved) {
            improved = false;
            for (int nb : links_[ep][layer]) {
                float d = dist(q.data(), vec(nb));
                if (d < d_ep) {
                    d_ep = d;
                    ep = nb;
                    improved = true;
                }
            }
        }
    }

    std::vector<std::pair<float, int>> results;
    search_layer(q.data(), ep, 0, std::max(ef_search, k), results);

    for (const auto& [d, id] : results) {
        out.emplace_back(static_cast<size_t>(id), 1.0f - d / 2.0f);
        if (static_cast<int>(out.size()) >= k) break;
    }
    return out;
}

std::vector<std::tuple<size_t, size_t, float>>
HnswIndex::pairs_within(float threshold, int k, int ef_search) const {
    std::vector<std::tuple<size_t, size_t, float>> pairs;
    for (size_t i = 0; i < data_.size(); ++i) {
        auto hits = knn(data_[i], k + 1, ef_search);
        for (const auto& [j, sim] : hits)
            if (j > i && sim >= threshold) pairs.emplace_back(i, j, sim);
    }
    return pairs;
}

}  // namespace base::similarity
