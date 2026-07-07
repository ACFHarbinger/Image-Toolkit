// ---------------------------------------------------------------------------
// base/include/web/recon.hpp — Entity Recon & Provenance data/discovery engine
//
// Native (C++) responsibilities for the Entity Recon tab:
//   * IdentityIndex — HNSW vector index mapping a face/CLIP embedding to the
//     parent dataset directory string (FirstName_LastName) + source path, for
//     millisecond local identity resolution.
//   * cutout_hash — stable xxHash64 digest of an alpha-cutout byte stream, used
//     as the SQLite provenance-cache key (dedupes reverse-search requests).
//
// NOTE: The original spec named Rust for this engine; the base module completed
// its Rust→C++ migration, so this is implemented in C++ and reuses the HNSW
// implementation from base.similarity.
// ---------------------------------------------------------------------------
#pragma once

#include <memory>
#include <string>
#include <tuple>
#include <vector>

#include <pybind11/pybind11.h>

#include "core/similarity.hpp"  // base::similarity::HnswIndex

namespace base::recon {

// One resolved candidate: (label, representative path, cosine similarity).
using IdentityMatch = std::tuple<std::string, std::string, float>;

class IdentityIndex {
public:
    IdentityIndex(int dim, int M = 16, int ef_construction = 200);

    // Register one embedding under a dataset label (FirstName_LastName) with the
    // originating file path.
    void add(const std::vector<float>& embedding,
             const std::string& label,
             const std::string& path);

    // Top-k nearest identities. Consecutive hits sharing a label are collapsed
    // to the single best-scoring representative so the caller gets distinct
    // identities, not duplicate rows for the same person.
    std::vector<IdentityMatch> query(const std::vector<float>& embedding,
                                     int k = 5, int ef_search = 64) const;

    size_t size() const { return labels_.size(); }
    std::vector<std::string> labels() const;

private:
    int dim_;
    std::unique_ptr<base::similarity::HnswIndex> hnsw_;
    std::vector<std::string> labels_;
    std::vector<std::string> paths_;
};

// Hex xxHash64 of an arbitrary byte buffer (the masked alpha cutout).
std::string cutout_hash(const std::string& bytes);

void register_recon(pybind11::module_& m);

}  // namespace base::recon
