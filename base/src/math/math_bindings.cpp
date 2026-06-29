// ---------------------------------------------------------------------------
// base/src/math/math_bindings.cpp — pybind11 wrappers for the math headers
// Phase 11 of Rust→C++ migration.
// Exposes: distance, stats, information, graph algorithms, PCA, MDS, t-SNE affinities.
// ---------------------------------------------------------------------------
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "math/distance.hpp"
#include "math/stats.hpp"
#include "math/information.hpp"
#include "math/graph.hpp"
#include "math/linalg.hpp"
#include "math/dim_reduce.hpp"

namespace py = pybind11;
using namespace base::math;

// ---------------------------------------------------------------------------
// Helpers: convert Matrix ↔ Python list[list[float]]
// ---------------------------------------------------------------------------

static std::vector<std::vector<double>> matrix_to_py(const Matrix& m) {
    std::vector<std::vector<double>> out(m.rows());
    for (int i = 0; i < m.rows(); ++i) out[i] = m.row(i);
    return out;
}

static Matrix py_to_matrix(const std::vector<std::vector<double>>& rows) {
    return Matrix::from_rows(rows);
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

void register_math(py::module_& m) {
    // ------------------------------------------------------------------
    // distance
    // ------------------------------------------------------------------
    py::module_ dist = m.def_submodule("distance", "Distance and similarity metrics.");

    dist.def("euclidean",
        [](const std::vector<double>& a, const std::vector<double>& b) {
            py::gil_scoped_release rel; return euclidean(a, b); },
        py::arg("a"), py::arg("b"), "Euclidean distance between two vectors.");

    dist.def("euclidean_sq",
        [](const std::vector<double>& a, const std::vector<double>& b) {
            py::gil_scoped_release rel; return euclidean_sq(a, b); },
        py::arg("a"), py::arg("b"), "Squared Euclidean distance.");

    dist.def("cosine_similarity",
        [](const std::vector<double>& a, const std::vector<double>& b) {
            py::gil_scoped_release rel; return cosine_similarity(a, b); },
        py::arg("a"), py::arg("b"), "Cosine similarity in [-1, 1].");

    dist.def("cosine_distance",
        [](const std::vector<double>& a, const std::vector<double>& b) {
            py::gil_scoped_release rel; return cosine_distance(a, b); },
        py::arg("a"), py::arg("b"), "Cosine distance = 1 - cosine_similarity.");

    dist.def("hamming",
        [](const std::vector<bool>& a, const std::vector<bool>& b) {
            py::gil_scoped_release rel; return hamming(a, b); },
        py::arg("a"), py::arg("b"), "Hamming distance between two bool vectors.");

    dist.def("bhattacharyya",
        [](const std::vector<double>& p, const std::vector<double>& q) {
            py::gil_scoped_release rel; return bhattacharyya(p, q); },
        py::arg("p"), py::arg("q"), "Bhattacharyya distance between two distributions.");

    dist.def("hellinger",
        [](const std::vector<double>& p, const std::vector<double>& q) {
            py::gil_scoped_release rel; return hellinger(p, q); },
        py::arg("p"), py::arg("q"), "Hellinger distance in [0, 1].");

    dist.def("manhattan",
        [](const std::vector<double>& a, const std::vector<double>& b) {
            py::gil_scoped_release rel; return manhattan(a, b); },
        py::arg("a"), py::arg("b"), "Manhattan (L1) distance.");

    // ------------------------------------------------------------------
    // stats
    // ------------------------------------------------------------------
    py::module_ st = m.def_submodule("stats", "Descriptive statistics.");

    st.def("mean",
        [](const std::vector<double>& xs) {
            py::gil_scoped_release rel; return mean(xs); },
        py::arg("xs"), "Arithmetic mean.");

    st.def("median",
        [](const std::vector<double>& xs) {
            py::gil_scoped_release rel; return median(xs); },
        py::arg("xs"), "Median.");

    st.def("std_dev",
        [](const std::vector<double>& xs, int ddof) {
            py::gil_scoped_release rel; return std_dev(xs, ddof); },
        py::arg("xs"), py::arg("ddof") = 0, "Standard deviation.");

    st.def("variance",
        [](const std::vector<double>& xs, int ddof) {
            py::gil_scoped_release rel; return variance(xs, ddof); },
        py::arg("xs"), py::arg("ddof") = 0, "Variance.");

    st.def("pearson",
        [](const std::vector<double>& a, const std::vector<double>& b) {
            py::gil_scoped_release rel; return pearson(a, b); },
        py::arg("a"), py::arg("b"), "Pearson correlation coefficient.");

    st.def("z_score",
        [](const std::vector<double>& xs) {
            py::gil_scoped_release rel; return z_score(xs); },
        py::arg("xs"), "Z-score normalisation.");

    st.def("min_max_normalize",
        [](const std::vector<double>& xs) {
            py::gil_scoped_release rel; return min_max_normalize(xs); },
        py::arg("xs"), "Min-max normalisation to [0, 1].");

    // ------------------------------------------------------------------
    // information
    // ------------------------------------------------------------------
    py::module_ info = m.def_submodule("information", "Information-theoretic metrics.");

    info.def("shannon_entropy",
        [](const std::vector<double>& p) {
            py::gil_scoped_release rel; return shannon_entropy(p); },
        py::arg("p"), "Shannon entropy in bits.");

    info.def("kl_divergence",
        [](const std::vector<double>& p, const std::vector<double>& q) {
            py::gil_scoped_release rel; return kl_divergence(p, q); },
        py::arg("p"), py::arg("q"), "KL divergence KL(p||q).");

    info.def("js_divergence",
        [](const std::vector<double>& p, const std::vector<double>& q) {
            py::gil_scoped_release rel; return js_divergence(p, q); },
        py::arg("p"), py::arg("q"), "Jensen-Shannon divergence.");

    info.def("js_distance",
        [](const std::vector<double>& p, const std::vector<double>& q) {
            py::gil_scoped_release rel; return js_distance(p, q); },
        py::arg("p"), py::arg("q"), "Jensen-Shannon distance (sqrt of JS divergence).");

    info.def("mutual_information",
        [](const std::vector<std::vector<double>>& joint) {
            py::gil_scoped_release rel; return mutual_information(joint); },
        py::arg("joint"), "Mutual information from a joint probability matrix.");

    // ------------------------------------------------------------------
    // graph
    // ------------------------------------------------------------------
    py::module_ gm = m.def_submodule("graph", "Graph algorithms.");

    py::class_<Graph>(gm, "Graph",
        "Weighted directed or undirected graph.")
        .def(py::init<bool>(), py::arg("directed") = false)
        .def("add_node", &Graph::add_node, py::arg("id"), py::arg("label") = "",
             "Add a node. Returns False if already exists.")
        .def("add_edge", &Graph::add_edge,
             py::arg("u"), py::arg("v"), py::arg("weight") = 1.0,
             "Add a weighted edge (undirected graphs add both directions).")
        .def("node_ids", &Graph::node_ids, "Sorted list of node IDs.")
        .def("neighbors", &Graph::neighbors, py::arg("u"),
             "Edges from node u.")
        .def_readonly("directed", &Graph::directed);

    py::class_<Graph::Edge>(gm, "Edge")
        .def_readonly("dst",    &Graph::Edge::dst)
        .def_readonly("weight", &Graph::Edge::weight);

    py::class_<KruskalEdge>(gm, "KruskalEdge")
        .def(py::init<>())
        .def_readwrite("u",      &KruskalEdge::u)
        .def_readwrite("v",      &KruskalEdge::v)
        .def_readwrite("weight", &KruskalEdge::weight);

    py::class_<SCCResult>(gm, "SCCResult")
        .def_readonly("components", &SCCResult::components,
                      "List of strongly-connected components (each is a sorted list of node IDs).")
        .def_readonly("comp_id", &SCCResult::comp_id,
                      "Component index per node (indexed by position in node_ids()).");

    gm.def("bfs", &bfs, py::arg("g"), py::arg("start"),
           "Breadth-first traversal order from start.");
    gm.def("dfs", &dfs, py::arg("g"), py::arg("start"),
           "Depth-first traversal order from start.");
    gm.def("kruskal_mst",
        [](int n, const std::vector<KruskalEdge>& edges) {
            py::gil_scoped_release rel; return kruskal_mst(n, edges); },
        py::arg("n"), py::arg("edges"),
        "Kruskal minimum spanning tree. n = number of nodes.");
    gm.def("kruskal_max_mst",
        [](int n, const std::vector<KruskalEdge>& edges) {
            py::gil_scoped_release rel; return kruskal_max_mst(n, edges); },
        py::arg("n"), py::arg("edges"),
        "Kruskal maximum spanning tree.");
    gm.def("tarjan_scc",
        [](const Graph& g) { py::gil_scoped_release rel; return tarjan_scc(g); },
        py::arg("g"), "Tarjan strongly-connected components.");
    gm.def("topological_sort",
        [](const Graph& g) { py::gil_scoped_release rel; return topological_sort(g); },
        py::arg("g"), "Topological sort (raises RuntimeError on cycle).");

    // ------------------------------------------------------------------
    // linalg (PCA)
    // ------------------------------------------------------------------
    py::module_ la = m.def_submodule("linalg", "Linear algebra (PCA, Matrix ops).");

    py::class_<Matrix>(la, "Matrix",
        "Row-major dense matrix (Eigen backend).")
        .def(py::init<int, int>(), py::arg("rows"), py::arg("cols"))
        .def_static("identity", &Matrix::identity, py::arg("n"))
        .def_static("from_rows", &Matrix::from_rows, py::arg("rows"))
        .def("rows", &Matrix::rows)
        .def("cols", &Matrix::cols)
        .def("get",  &Matrix::get, py::arg("r"), py::arg("c"))
        .def("set",  &Matrix::set, py::arg("r"), py::arg("c"), py::arg("v"))
        .def("row",  &Matrix::row, py::arg("r"))
        .def("transpose", &Matrix::transpose)
        .def("mul",   &Matrix::mul,   py::arg("rhs"))
        .def("add",   &Matrix::add,   py::arg("rhs"))
        .def("sub",   &Matrix::sub,   py::arg("rhs"))
        .def("scale", &Matrix::scale, py::arg("s"))
        .def("to_list", [](const Matrix& m) { return matrix_to_py(m); },
             "Convert to list[list[float]].");

    py::class_<PCAResult>(la, "PCAResult")
        .def_property_readonly("scores",
            [](const PCAResult& r) { return matrix_to_py(r.scores); },
            "Projected data (n_samples × n_components).")
        .def_property_readonly("components",
            [](const PCAResult& r) { return matrix_to_py(r.components); },
            "Principal axes (n_components × n_features).")
        .def_readonly("explained_variance_ratio", &PCAResult::explained_variance_ratio);

    la.def("pca",
        [](const std::vector<std::vector<double>>& data, int n_components) {
            py::gil_scoped_release rel;
            return pca(py_to_matrix(data), n_components);
        },
        py::arg("data"), py::arg("n_components"),
        "PCA on data (n_samples x n_features). Returns PCAResult.");

    // ------------------------------------------------------------------
    // dim_reduce (MDS, t-SNE affinities)
    // ------------------------------------------------------------------
    py::module_ dr = m.def_submodule("dim_reduce", "Dimensionality reduction.");

    dr.def("mds",
        [](const std::vector<std::vector<double>>& dist_mat, int n_components) {
            py::gil_scoped_release rel;
            return matrix_to_py(mds(py_to_matrix(dist_mat), n_components));
        },
        py::arg("dist_mat"), py::arg("n_components") = 2,
        "Classical MDS on a distance matrix. Returns list[list[float]] (n × n_components).");

    dr.def("tsne_affinities",
        [](const std::vector<std::vector<double>>& data, double perplexity) {
            py::gil_scoped_release rel;
            return matrix_to_py(tsne_affinities(py_to_matrix(data), perplexity));
        },
        py::arg("data"), py::arg("perplexity") = 30.0,
        "Compute symmetric t-SNE affinity matrix P from raw data. "
        "Returns list[list[float]] (n × n).");
}
