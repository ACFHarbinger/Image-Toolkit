// ---------------------------------------------------------------------------
// base/src/core/similarity/bindings.cpp — pybind11 API for base.similarity
// ---------------------------------------------------------------------------
#include "core/similarity.hpp"

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <stdexcept>

namespace py = pybind11;

namespace base::similarity {

namespace {

// Batch perceptual + exact hashing with the GIL released and OpenMP fan-out.
struct HashRecord {
    std::string path;
    bool ok = false;
    std::string xxh64;
    std::string phash, dhash, whash;
};

std::vector<HashRecord> compute_hashes_impl(const std::vector<std::string>& paths,
                                            int hash_size, bool with_exact) {
    int n = static_cast<int>(paths.size());
    std::vector<HashRecord> out(n);
#pragma omp parallel for schedule(dynamic)
    for (int i = 0; i < n; ++i) {
        out[i].path = paths[i];
        if (with_exact) out[i].xxh64 = xxh64_file(paths[i]);
        PerceptualHashes h = compute_perceptual_hashes(paths[i], hash_size);
        out[i].ok = h.ok;
        if (h.ok) {
            out[i].phash = bithash_to_hex(h.phash);
            out[i].dhash = bithash_to_hex(h.dhash);
            out[i].whash = bithash_to_hex(h.whash);
        }
    }
    return out;
}

}  // namespace

void register_similarity(py::module_& m) {
    m.doc() = "Similarity Finder engine: exact/perceptual hashing, VP-tree & HNSW "
              "indexes, SSIM/feature verification and visual diffing.";

    // ------------------------------------------------------------------ Tier 1
    m.def("xxh64_file",
        [](const std::string& path) {
            py::gil_scoped_release rel;
            return xxh64_file(path);
        },
        py::arg("path"),
        "xxHash64 hex digest of a file (empty string on I/O error).");

    m.def("xxh64_files",
        [](const std::vector<std::string>& paths) {
            py::gil_scoped_release rel;
            int n = static_cast<int>(paths.size());
            std::vector<std::string> out(n);
#pragma omp parallel for schedule(dynamic)
            for (int i = 0; i < n; ++i) out[i] = xxh64_file(paths[i]);
            return out;
        },
        py::arg("paths"),
        "Parallel xxHash64 digests for a list of files.");

    // ------------------------------------------------------------------ Tier 2
    m.def("compute_hashes",
        [](const std::vector<std::string>& paths, int hash_size, bool with_exact) {
            std::vector<HashRecord> records;
            {
                py::gil_scoped_release rel;
                records = compute_hashes_impl(paths, hash_size, with_exact);
            }
            py::list out;
            for (const auto& r : records) {
                py::dict d;
                d["path"] = r.path;
                d["ok"] = r.ok;
                d["xxh64"] = r.xxh64;
                d["phash"] = r.phash;
                d["dhash"] = r.dhash;
                d["whash"] = r.whash;
                out.append(std::move(d));
            }
            return out;
        },
        py::arg("paths"), py::arg("hash_size") = 8, py::arg("with_exact") = true,
        "Batch xxHash64 + pHash/dHash/wHash (hex strings). hash_size ∈ {8, 16, 32}.");

    m.def("hamming",
        [](const std::string& hex_a, const std::string& hex_b) {
            return hamming_distance(bithash_from_hex(hex_a), bithash_from_hex(hex_b));
        },
        py::arg("hash_a"), py::arg("hash_b"),
        "Hamming distance between two hex-encoded hashes.");

    // Replaces the Rust phash_engine.compute_phash: pHash a raw image byte
    // buffer (no disk round-trip) and return it hex-encoded.
    m.def("phash_bytes",
        [](const py::bytes& data, int hash_size) -> std::string {
            std::string s = data;
            py::gil_scoped_release rel;
            BitHash h = phash_from_buffer(s.data(), s.size(), hash_size);
            return bithash_to_hex(h);
        },
        py::arg("data"), py::arg("hash_size") = 8,
        "Perceptual hash (hex) of an in-memory image buffer; '' on decode error.");

    // Replaces the Rust phash_engine.batch_hamming_distance: one query hash
    // against many candidates in a single call, returning (index, distance).
    m.def("batch_hamming",
        [](const std::string& query_hex,
           const std::vector<std::string>& candidate_hex) {
            py::gil_scoped_release rel;
            BitHash q = bithash_from_hex(query_hex);
            std::vector<std::pair<size_t, uint32_t>> out;
            out.reserve(candidate_hex.size());
            for (size_t i = 0; i < candidate_hex.size(); ++i) {
                if (candidate_hex[i].empty()) continue;
                out.emplace_back(i, hamming_distance(q, bithash_from_hex(candidate_hex[i])));
            }
            return out;
        },
        py::arg("query_hash"), py::arg("candidate_hashes"),
        "Hamming distance of query_hash against each candidate; returns "
        "(index, distance) pairs (skipping empty candidates).");

    m.def("consensus_confidence",
        [](const std::string& pa, const std::string& da, const std::string& wa,
           const std::string& pb, const std::string& db, const std::string& wb,
           int hash_size) {
            PerceptualHashes a, b;
            a.ok = b.ok = true;
            a.phash = bithash_from_hex(pa); a.dhash = bithash_from_hex(da);
            a.whash = bithash_from_hex(wa);
            b.phash = bithash_from_hex(pb); b.dhash = bithash_from_hex(db);
            b.whash = bithash_from_hex(wb);
            return consensus_confidence(a, b, hash_size);
        },
        py::arg("phash_a"), py::arg("dhash_a"), py::arg("whash_a"),
        py::arg("phash_b"), py::arg("dhash_b"), py::arg("whash_b"),
        py::arg("hash_size") = 8,
        "Weighted multi-hash consensus confidence in [0, 1].");

    m.def("hash_pairs_within",
        [](const std::vector<std::string>& phashes,
           const std::vector<std::string>& dhashes,
           const std::vector<std::string>& whashes,
           uint32_t hamming_threshold, int hash_size) {
            if (phashes.size() != dhashes.size() || phashes.size() != whashes.size())
                throw std::invalid_argument("hash lists must have equal length");
            py::gil_scoped_release rel;

            size_t n = phashes.size();
            std::vector<PerceptualHashes> all(n);
            std::vector<BitHash> ph(n);
            for (size_t i = 0; i < n; ++i) {
                all[i].ok = true;
                all[i].phash = bithash_from_hex(phashes[i]);
                all[i].dhash = bithash_from_hex(dhashes[i]);
                all[i].whash = bithash_from_hex(whashes[i]);
                ph[i] = all[i].phash;
            }
            VpTree tree(std::move(ph));
            auto raw = tree.pairs_within(hamming_threshold);

            std::vector<std::tuple<size_t, size_t, uint32_t, double>> out;
            out.reserve(raw.size());
            for (const auto& [i, j, d] : raw)
                out.emplace_back(i, j, d,
                                 consensus_confidence(all[i], all[j], hash_size));
            return out;
        },
        py::arg("phashes"), py::arg("dhashes"), py::arg("whashes"),
        py::arg("hamming_threshold") = 10, py::arg("hash_size") = 8,
        "VP-tree candidate pairs (i, j, phash_distance, consensus_confidence) with "
        "pHash Hamming distance <= threshold.");

    // ------------------------------------------------------------ VP-tree class
    py::class_<VpTree>(m, "VpTree",
        "Vantage-point tree over hex-encoded binary hashes (Hamming metric).")
        .def(py::init([](const std::vector<std::string>& hex_hashes) {
                 std::vector<BitHash> items;
                 items.reserve(hex_hashes.size());
                 for (const auto& h : hex_hashes) items.push_back(bithash_from_hex(h));
                 py::gil_scoped_release rel;
                 return new VpTree(std::move(items));
             }),
             py::arg("hashes"))
        .def("query",
             [](const VpTree& t, const std::string& hex, uint32_t radius) {
                 auto q = bithash_from_hex(hex);
                 py::gil_scoped_release rel;
                 return t.query_radius(q, radius);
             },
             py::arg("hash"), py::arg("radius"),
             "All (index, distance) within Hamming radius of `hash`.")
        .def("pairs_within",
             [](const VpTree& t, uint32_t radius) {
                 py::gil_scoped_release rel;
                 return t.pairs_within(radius);
             },
             py::arg("radius"),
             "All unordered (i, j, distance) pairs within Hamming radius.")
        .def_property_readonly("size", &VpTree::size);

    // --------------------------------------------------------------- HNSW class
    py::class_<HnswIndex>(m, "HnswIndex",
        "HNSW approximate nearest-neighbour index (cosine similarity).")
        .def(py::init<int, int, int, uint64_t>(),
             py::arg("dim"), py::arg("M") = 16, py::arg("ef_construction") = 200,
             py::arg("seed") = 42)
        .def("add_items",
             [](HnswIndex& idx, py::array_t<float, py::array::c_style |
                                                   py::array::forcecast> arr) {
                 if (arr.ndim() != 2)
                     throw std::invalid_argument("expected a 2D array [n, dim]");
                 auto buf = arr.unchecked<2>();
                 py::gil_scoped_release rel;
                 for (py::ssize_t r = 0; r < buf.shape(0); ++r) {
                     std::vector<float> v(buf.shape(1));
                     for (py::ssize_t c = 0; c < buf.shape(1); ++c)
                         v[c] = buf(r, c);
                     idx.add(v);
                 }
             },
             py::arg("vectors"),
             "Insert a [n, dim] float32 matrix of embeddings.")
        .def("knn",
             [](const HnswIndex& idx, const std::vector<float>& query, int k,
                int ef_search) {
                 py::gil_scoped_release rel;
                 return idx.knn(query, k, ef_search);
             },
             py::arg("query"), py::arg("k") = 10, py::arg("ef_search") = 64,
             "k nearest neighbours as (index, cosine_similarity) pairs.")
        .def("pairs_within",
             [](const HnswIndex& idx, float threshold, int k, int ef_search) {
                 py::gil_scoped_release rel;
                 return idx.pairs_within(threshold, k, ef_search);
             },
             py::arg("threshold"), py::arg("k") = 16, py::arg("ef_search") = 64,
             "All unordered (i, j, cosine_similarity) pairs with sim >= threshold.")
        .def_property_readonly("size", &HnswIndex::size);

    // ------------------------------------------------------------------ Tier 3
    m.def("ssim",
        [](const std::string& a, const std::string& b, int resize_to) {
            py::gil_scoped_release rel;
            return ssim_score(a, b, resize_to);
        },
        py::arg("path_a"), py::arg("path_b"), py::arg("resize_to") = 256,
        "Mean SSIM in [-1, 1] (−1.0 on read error).");

    m.def("match_features",
        [](const std::string& a, const std::string& b, const std::string& method,
           int max_features, double lowe_ratio, double ransac_threshold) {
            FeatureMatchResult r;
            {
                py::gil_scoped_release rel;
                r = match_features(a, b, method, max_features, lowe_ratio,
                                   ransac_threshold);
            }
            py::dict d;
            d["ok"] = r.ok;
            d["keypoints_a"] = r.keypoints_a;
            d["keypoints_b"] = r.keypoints_b;
            d["good_matches"] = r.good_matches;
            d["inliers"] = r.inliers;
            d["match_ratio"] = r.match_ratio;
            d["inlier_ratio"] = r.inlier_ratio;
            d["confidence"] = r.confidence;
            return d;
        },
        py::arg("path_a"), py::arg("path_b"), py::arg("method") = "orb",
        py::arg("max_features") = 1000, py::arg("lowe_ratio") = 0.75,
        py::arg("ransac_threshold") = 5.0,
        "ORB/SIFT matching with Lowe's ratio test + RANSAC homography verification.");

    // ------------------------------------------------------------------ Diffing
    m.def("diff_mask",
        [](const std::string& a, const std::string& b, const std::string& out_path,
           int tolerance) {
            DiffResult r;
            {
                py::gil_scoped_release rel;
                r = diff_mask(a, b, out_path, tolerance);
            }
            py::dict d;
            d["ok"] = r.ok;
            d["changed_ratio"] = r.changed_ratio;
            d["out_path"] = r.out_path;
            return d;
        },
        py::arg("path_a"), py::arg("path_b"), py::arg("out_path"),
        py::arg("tolerance") = 12,
        "Write a neon-green difference-mask PNG to out_path; returns "
        "{ok, changed_ratio, out_path}.");
}

}  // namespace base::similarity
