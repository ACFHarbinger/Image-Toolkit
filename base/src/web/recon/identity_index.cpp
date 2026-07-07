// ---------------------------------------------------------------------------
// base/src/web/recon/identity_index.cpp
// HNSW-backed identity resolution index for the Entity Recon tab.
// ---------------------------------------------------------------------------
#include "web/recon.hpp"

#include <algorithm>
#include <unordered_map>

namespace base::recon {

IdentityIndex::IdentityIndex(int dim, int M, int ef_construction)
    : dim_(dim),
      hnsw_(std::make_unique<base::similarity::HnswIndex>(dim, M, ef_construction)) {}

void IdentityIndex::add(const std::vector<float>& embedding,
                        const std::string& label,
                        const std::string& path) {
    hnsw_->add(embedding);
    labels_.push_back(label);
    paths_.push_back(path);
}

std::vector<IdentityMatch> IdentityIndex::query(const std::vector<float>& embedding,
                                                int k, int ef_search) const {
    // Over-fetch so that after collapsing duplicate labels we still return ~k
    // distinct identities.
    auto raw = hnsw_->knn(embedding, k * 4, ef_search);

    std::unordered_map<std::string, float> best;   // label -> best similarity
    std::unordered_map<std::string, std::string> rep;  // label -> path
    std::vector<std::string> order;                 // first-seen label order

    for (const auto& [idx, sim] : raw) {
        if (idx >= labels_.size()) continue;
        const std::string& label = labels_[idx];
        auto it = best.find(label);
        if (it == best.end()) {
            best[label] = sim;
            rep[label] = paths_[idx];
            order.push_back(label);
        } else if (sim > it->second) {
            it->second = sim;
            rep[label] = paths_[idx];
        }
    }

    std::vector<IdentityMatch> matches;
    matches.reserve(order.size());
    for (const auto& label : order)
        matches.emplace_back(label, rep[label], best[label]);

    std::sort(matches.begin(), matches.end(),
              [](const IdentityMatch& a, const IdentityMatch& b) {
                  return std::get<2>(a) > std::get<2>(b);
              });
    if (static_cast<int>(matches.size()) > k) matches.resize(k);
    return matches;
}

std::vector<std::string> IdentityIndex::labels() const { return labels_; }

std::string cutout_hash(const std::string& bytes) {
    uint64_t h = base::similarity::xxh64_buffer(bytes.data(), bytes.size(), 0);
    static const char* hex = "0123456789abcdef";
    std::string out(16, '0');
    for (int i = 15; i >= 0; --i) {
        out[i] = hex[h & 0xF];
        h >>= 4;
    }
    return out;
}

}  // namespace base::recon
