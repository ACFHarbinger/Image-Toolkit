// ---------------------------------------------------------------------------
// base/include/core/similarity.hpp — Similarity Finder detection engine
//
// Tier 1: exact match      — xxHash64 (XXH64) file digests
// Tier 2: consensus hashes — pHash (DCT) / dHash / wHash (Haar), 8/16/32 sizes
// Tier 3: structural       — SSIM + ORB/SIFT feature matching w/ RANSAC verify
// Tier 4: semantic         — HNSW index over externally-computed embeddings
//
// Spatial indexing: VP-tree (Hamming) for hash lookups, HNSW for vectors.
// All heavy loops run with the GIL released; OpenMP parallel where applicable.
// ---------------------------------------------------------------------------
#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include <pybind11/pybind11.h>

namespace base::similarity {

// A multi-word binary hash (hash_size 8 -> 1 word, 16 -> 4 words, 32 -> 16 words).
using BitHash = std::vector<uint64_t>;

// ---------------------------------------------------------------------------
// Tier 1 — exact content hashing
// ---------------------------------------------------------------------------
uint64_t xxh64_buffer(const void* data, size_t len, uint64_t seed = 0);
std::string xxh64_file(const std::string& path);

// ---------------------------------------------------------------------------
// Tier 2 — perceptual hashing
// ---------------------------------------------------------------------------
struct PerceptualHashes {
    bool ok = false;
    BitHash phash;   // DCT low-frequency hash
    BitHash dhash;   // horizontal gradient hash
    BitHash whash;   // Haar-wavelet LL hash
};

PerceptualHashes compute_perceptual_hashes(const std::string& path, int hash_size);

// Decode an in-memory image buffer (JPEG/PNG/WebP/…) and compute its pHash
// only — used by the subreddit sweep which never touches disk. Empty on
// decode failure.
BitHash phash_from_buffer(const void* data, size_t len, int hash_size);

uint32_t hamming_distance(const BitHash& a, const BitHash& b);

std::string bithash_to_hex(const BitHash& h);
BitHash bithash_from_hex(const std::string& hex);

// Consensus confidence in [0, 1] combining the three hash distances.
double consensus_confidence(const PerceptualHashes& a, const PerceptualHashes& b,
                            int hash_size);

// ---------------------------------------------------------------------------
// VP-tree over Hamming space
// ---------------------------------------------------------------------------
class VpTree {
public:
    explicit VpTree(std::vector<BitHash> items);
    // (index, distance) of all items within `radius` of `query`
    std::vector<std::pair<size_t, uint32_t>> query_radius(const BitHash& query,
                                                          uint32_t radius) const;
    // all unordered pairs (i, j, dist) with dist <= radius  — O(N log N) expected
    std::vector<std::tuple<size_t, size_t, uint32_t>> pairs_within(uint32_t radius) const;
    size_t size() const { return items_.size(); }

private:
    struct Node {
        int index = -1;
        uint32_t threshold = 0;
        int left = -1;
        int right = -1;
    };
    int build(std::vector<int>& idx, int lo, int hi);
    void search(int node, const BitHash& q, uint32_t radius,
                std::vector<std::pair<size_t, uint32_t>>& out) const;

    std::vector<BitHash> items_;
    std::vector<Node> nodes_;
    int root_ = -1;
};

// ---------------------------------------------------------------------------
// HNSW over float vectors (cosine similarity)
// ---------------------------------------------------------------------------
class HnswIndex {
public:
    HnswIndex(int dim, int M = 16, int ef_construction = 200, uint64_t seed = 42);

    void add(const std::vector<float>& vec);
    // (index, cosine_similarity) of the k nearest neighbours
    std::vector<std::pair<size_t, float>> knn(const std::vector<float>& query,
                                              int k, int ef_search = 64) const;
    // all unordered pairs with cosine similarity >= threshold (via per-node kNN)
    std::vector<std::tuple<size_t, size_t, float>> pairs_within(float threshold,
                                                                int k = 16,
                                                                int ef_search = 64) const;
    size_t size() const { return data_.size(); }

private:
    // squared-L2 over L2-normalised vectors: d = 2 - 2*cos  → monotone with cosine
    float dist(const float* a, const float* b) const;
    const float* vec(size_t id) const { return data_[id].data(); }
    int random_level();
    void search_layer(const float* q, int entry, int layer, int ef,
                      std::vector<std::pair<float, int>>& results) const;
    std::vector<int> select_neighbors(const float* q,
                                      std::vector<std::pair<float, int>>& cand,
                                      int M) const;

    int dim_;
    int M_;
    int max_M0_;
    int ef_construction_;
    double level_mult_;
    uint64_t rng_state_;
    int entry_point_ = -1;
    int max_level_ = -1;
    std::vector<std::vector<float>> data_;                 // normalised vectors
    std::vector<int> levels_;                              // per node top layer
    std::vector<std::vector<std::vector<int>>> links_;     // [node][layer] -> neighbours
};

// ---------------------------------------------------------------------------
// Tier 3 — structural / geometric verification
// ---------------------------------------------------------------------------
struct FeatureMatchResult {
    bool ok = false;
    int keypoints_a = 0;
    int keypoints_b = 0;
    int good_matches = 0;   // after Lowe's ratio test
    int inliers = 0;        // after RANSAC homography
    double match_ratio = 0.0;
    double inlier_ratio = 0.0;
    double confidence = 0.0;
};

FeatureMatchResult match_features(const std::string& path_a, const std::string& path_b,
                                  const std::string& method,   // "orb" | "sift"
                                  int max_features, double lowe_ratio,
                                  double ransac_threshold);

// Mean SSIM over grayscale images resized to `resize_to` (0 = no resize; B is
// resized to A's geometry).
double ssim_score(const std::string& path_a, const std::string& path_b, int resize_to);

// ---------------------------------------------------------------------------
// Visual diffing — difference mask with neon-green highlight
// ---------------------------------------------------------------------------
struct DiffResult {
    bool ok = false;
    double changed_ratio = 0.0;   // fraction of pixels above tolerance
    std::string out_path;
};

DiffResult diff_mask(const std::string& path_a, const std::string& path_b,
                     const std::string& out_path, int tolerance);

void register_similarity(pybind11::module_& m);

}  // namespace base::similarity
