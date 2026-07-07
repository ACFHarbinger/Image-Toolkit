// ---------------------------------------------------------------------------
// base/src/web/recon/bindings.cpp — pybind11 API for base.recon
// ---------------------------------------------------------------------------
#include "web/recon.hpp"

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <stdexcept>

namespace py = pybind11;

namespace base::recon {

void register_recon(py::module_& m) {
    m.doc() = "Entity Recon data/discovery engine: HNSW identity index + "
              "alpha-cutout hashing.";

    py::class_<IdentityIndex>(m, "IdentityIndex",
        "HNSW identity index mapping embeddings to dataset labels "
        "(FirstName_LastName) and source paths.")
        .def(py::init<int, int, int>(),
             py::arg("dim"), py::arg("M") = 16, py::arg("ef_construction") = 200)
        .def("add",
             [](IdentityIndex& idx, const std::vector<float>& emb,
                const std::string& label, const std::string& path) {
                 py::gil_scoped_release rel;
                 idx.add(emb, label, path);
             },
             py::arg("embedding"), py::arg("label"), py::arg("path"),
             "Register one embedding under a dataset label + source path.")
        .def("add_batch",
             [](IdentityIndex& idx,
                py::array_t<float, py::array::c_style | py::array::forcecast> arr,
                const std::vector<std::string>& labels,
                const std::vector<std::string>& paths) {
                 if (arr.ndim() != 2)
                     throw std::invalid_argument("embeddings must be 2D [n, dim]");
                 if (static_cast<size_t>(arr.shape(0)) != labels.size() ||
                     labels.size() != paths.size())
                     throw std::invalid_argument("row / label / path count mismatch");
                 auto buf = arr.unchecked<2>();
                 py::gil_scoped_release rel;
                 for (py::ssize_t r = 0; r < buf.shape(0); ++r) {
                     std::vector<float> v(buf.shape(1));
                     for (py::ssize_t c = 0; c < buf.shape(1); ++c) v[c] = buf(r, c);
                     idx.add(v, labels[r], paths[r]);
                 }
             },
             py::arg("embeddings"), py::arg("labels"), py::arg("paths"),
             "Bulk-register a [n, dim] matrix with parallel label/path lists.")
        .def("query",
             [](const IdentityIndex& idx, const std::vector<float>& emb, int k,
                int ef_search) {
                 py::gil_scoped_release rel;
                 return idx.query(emb, k, ef_search);
             },
             py::arg("embedding"), py::arg("k") = 5, py::arg("ef_search") = 64,
             "Top-k distinct identities as (label, path, cosine_similarity).")
        .def("labels", &IdentityIndex::labels)
        .def_property_readonly("size", &IdentityIndex::size);

    m.def("cutout_hash",
        [](const py::bytes& data) {
            std::string s = data;
            py::gil_scoped_release rel;
            return cutout_hash(s);
        },
        py::arg("data"),
        "Stable xxHash64 hex digest of an alpha-cutout byte stream "
        "(provenance-cache key).");
}

}  // namespace base::recon
