// ---------------------------------------------------------------------------
// base/src/math/math_bindings.cpp — pybind11 wrappers for the math headers
// Phase 11 of Rust→C++ migration; extended in Phase 13 with full parity.
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

    dist.def("chebyshev",
        [](const std::vector<double>& a, const std::vector<double>& b) {
            py::gil_scoped_release rel; return chebyshev(a, b); },
        py::arg("a"), py::arg("b"), "Chebyshev (L∞) distance: max_i |a_i - b_i|.");

    dist.def("minkowski",
        [](const std::vector<double>& a, const std::vector<double>& b, double p) {
            py::gil_scoped_release rel; return minkowski(a, b, p); },
        py::arg("a"), py::arg("b"), py::arg("p"),
        "Minkowski distance with exponent p (p>=1). p=1->Manhattan, p=2->Euclidean.");

    dist.def("pairwise_distance_matrix",
        [](const std::vector<std::vector<double>>& pts) {
            py::gil_scoped_release rel; return pairwise_distance_matrix(pts); },
        py::arg("points"),
        "Full n x n pairwise Euclidean distance matrix.");

    dist.def("condensed_distance_matrix",
        [](const std::vector<std::vector<double>>& pts) {
            py::gil_scoped_release rel; return condensed_distance_matrix(pts); },
        py::arg("points"),
        "Condensed (upper-triangle) pairwise Euclidean distances, length n*(n-1)/2.");

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

    st.def("sample_variance",
        [](const std::vector<double>& xs) {
            py::gil_scoped_release rel; return sample_variance(xs); },
        py::arg("xs"), "Sample variance (ddof=1).");

    st.def("sample_std_dev",
        [](const std::vector<double>& xs) {
            py::gil_scoped_release rel; return sample_std_dev(xs); },
        py::arg("xs"), "Sample standard deviation (ddof=1).");

    st.def("pearson",
        [](const std::vector<double>& a, const std::vector<double>& b) {
            py::gil_scoped_release rel; return pearson(a, b); },
        py::arg("a"), py::arg("b"), "Pearson correlation coefficient.");

    st.def("covariance",
        [](const std::vector<double>& xs, const std::vector<double>& ys) {
            py::gil_scoped_release rel; return covariance(xs, ys); },
        py::arg("xs"), py::arg("ys"), "Population covariance of two equal-length series.");

    st.def("z_score",
        [](const std::vector<double>& xs) {
            py::gil_scoped_release rel; return z_score(xs); },
        py::arg("xs"), "Z-score normalisation.");

    st.def("min_max_normalize",
        [](const std::vector<double>& xs) {
            py::gil_scoped_release rel; return min_max_normalize(xs); },
        py::arg("xs"), "Min-max normalisation to [0, 1].");

    st.def("min_val",
        [](const std::vector<double>& xs) {
            py::gil_scoped_release rel; return min_val(xs); },
        py::arg("xs"), "Minimum value (+inf for empty input).");

    st.def("max_val",
        [](const std::vector<double>& xs) {
            py::gil_scoped_release rel; return max_val(xs); },
        py::arg("xs"), "Maximum value (-inf for empty input).");

    st.def("percentile",
        [](const std::vector<double>& xs, double p) {
            py::gil_scoped_release rel; return percentile(xs, p); },
        py::arg("xs"), py::arg("p"),
        "Nearest-rank percentile. p in [0, 1]. Returns NaN for empty input.");

    st.def("iqr",
        [](const std::vector<double>& xs) {
            py::gil_scoped_release rel; return iqr(xs); },
        py::arg("xs"), "Interquartile range Q3 - Q1.");

    st.def("histogram",
        [](const std::vector<double>& xs, std::size_t bins) {
            py::gil_scoped_release rel;
            auto [edges, counts] = histogram(xs, bins);
            return py::make_tuple(edges, counts);
        },
        py::arg("xs"), py::arg("bins"),
        "Equal-width histogram. Returns (bin_edges, counts) tuple.");

    st.def("counts_to_probs",
        [](const std::vector<std::size_t>& counts) {
            py::gil_scoped_release rel; return counts_to_probs(counts); },
        py::arg("counts"),
        "Convert raw counts to normalised probabilities summing to 1.");

    st.def("covariance_matrix",
        [](const std::vector<std::vector<double>>& data) {
            py::gil_scoped_release rel; return covariance_matrix(data); },
        py::arg("data"),
        "Population covariance matrix for n x d data. Returns d*d flat row-major vector.");

    // ------------------------------------------------------------------
    // information
    // ------------------------------------------------------------------
    py::module_ info = m.def_submodule("information", "Information-theoretic metrics.");

    info.def("shannon_entropy",
        [](const std::vector<double>& p) {
            py::gil_scoped_release rel; return shannon_entropy(p); },
        py::arg("p"), "Shannon entropy in bits.");

    info.def("entropy_nats",
        [](const std::vector<double>& p) {
            py::gil_scoped_release rel; return entropy_nats(p); },
        py::arg("p"), "Shannon entropy in nats (natural log base).");

    info.def("empirical_entropy",
        [](const std::vector<std::size_t>& counts) {
            py::gil_scoped_release rel; return empirical_entropy(counts); },
        py::arg("counts"),
        "Shannon entropy computed from raw integer counts (normalises internally).");

    info.def("joint_entropy",
        [](const std::vector<std::vector<std::size_t>>& joint) {
            py::gil_scoped_release rel; return joint_entropy(joint); },
        py::arg("joint_counts"),
        "Joint entropy H(X,Y) from a 2-D count matrix.");

    info.def("conditional_entropy",
        [](const std::vector<std::vector<std::size_t>>& joint) {
            py::gil_scoped_release rel; return conditional_entropy(joint); },
        py::arg("joint_counts"),
        "Conditional entropy H(Y|X) = H(X,Y) - H(X) from a joint count matrix.");

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

    info.def("total_variation",
        [](const std::vector<double>& p, const std::vector<double>& q) {
            py::gil_scoped_release rel; return total_variation(p, q); },
        py::arg("p"), py::arg("q"),
        "Total variation distance TV(P,Q) = half * sum|P_i - Q_i|.");

    info.def("mutual_information",
        [](const std::vector<std::vector<double>>& joint) {
            py::gil_scoped_release rel; return mutual_information(joint); },
        py::arg("joint"), "Mutual information from a joint probability matrix.");

    info.def("mutual_information_discrete",
        [](const std::vector<std::vector<std::size_t>>& joint) {
            py::gil_scoped_release rel; return mutual_information_discrete(joint); },
        py::arg("joint_counts"),
        "I(X;Y) = H(X)+H(Y)-H(X,Y) from a joint count matrix.");

    info.def("normalised_mutual_information",
        [](const std::vector<std::vector<std::size_t>>& joint) {
            py::gil_scoped_release rel; return normalised_mutual_information(joint); },
        py::arg("joint_counts"),
        "NMI(X;Y) = I(X;Y)/sqrt(H(X)*H(Y)) in [0, 1].");

    info.def("cross_entropy",
        [](const std::vector<double>& p, const std::vector<double>& q) {
            py::gil_scoped_release rel; return cross_entropy(p, q); },
        py::arg("p"), py::arg("q"),
        "Cross-entropy H(P,Q) = -sum P_i log2 Q_i. Returns +inf if Q_i=0 where P_i>0.");

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
    gm.def("connected_components",
        [](const Graph& g) { py::gil_scoped_release rel; return connected_components(g); },
        py::arg("g"),
        "Connected components of an undirected graph. "
        "Returns list of sorted component node lists.");

    // ------------------------------------------------------------------
    // linalg (PCA, vector ops)
    // ------------------------------------------------------------------
    py::module_ la = m.def_submodule("linalg", "Linear algebra (PCA, Matrix ops, vector utils).");

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
            "Projected data (n_samples x n_components).")
        .def_property_readonly("components",
            [](const PCAResult& r) { return matrix_to_py(r.components); },
            "Principal axes (n_components x n_features).")
        .def_readonly("explained_variance_ratio", &PCAResult::explained_variance_ratio);

    la.def("pca",
        [](const std::vector<std::vector<double>>& data, int n_components) {
            py::gil_scoped_release rel;
            return pca(py_to_matrix(data), n_components);
        },
        py::arg("data"), py::arg("n_components"),
        "PCA on data (n_samples x n_features). Returns PCAResult.");

    la.def("dot",
        [](const std::vector<double>& a, const std::vector<double>& b) {
            py::gil_scoped_release rel; return dot(a, b); },
        py::arg("a"), py::arg("b"), "Dot product of two equal-length vectors.");

    la.def("norm",
        [](const std::vector<double>& v) {
            py::gil_scoped_release rel; return norm(v); },
        py::arg("v"), "Euclidean norm of a vector.");

    la.def("normalize",
        [](const std::vector<double>& v) {
            py::gil_scoped_release rel; return normalize(v); },
        py::arg("v"), "Return v / ||v||. Raises ValueError for zero vector.");

    la.def("vec_sub",
        [](const std::vector<double>& a, const std::vector<double>& b) {
            py::gil_scoped_release rel; return vec_sub(a, b); },
        py::arg("a"), py::arg("b"), "Element-wise a - b.");

    la.def("vec_add",
        [](const std::vector<double>& a, const std::vector<double>& b) {
            py::gil_scoped_release rel; return vec_add(a, b); },
        py::arg("a"), py::arg("b"), "Element-wise a + b.");

    la.def("vec_scale",
        [](const std::vector<double>& v, double s) {
            py::gil_scoped_release rel; return vec_scale(v, s); },
        py::arg("v"), py::arg("s"), "Scalar multiplication s * v.");

    la.def("gram_schmidt_step",
        [](const std::vector<double>& v,
           const std::vector<std::vector<double>>& basis) {
            py::gil_scoped_release rel; return gram_schmidt_step(v, basis); },
        py::arg("v"), py::arg("basis"),
        "Subtract projections of v onto each orthonormal basis vector.");

    la.def("pca_2d",
        [](const std::vector<std::vector<double>>& data) {
            py::gil_scoped_release rel;
            auto pts = pca_2d(data);
            std::vector<std::array<double, 2>> out(pts);
            return out;
        },
        py::arg("data"),
        "Project data onto the first two principal components. "
        "Returns list of [pc1, pc2] pairs.");

    // ------------------------------------------------------------------
    // dim_reduce (MDS, t-SNE affinities, geodesic distances)
    // ------------------------------------------------------------------
    py::module_ dr = m.def_submodule("dim_reduce", "Dimensionality reduction.");

    dr.def("mds",
        [](const std::vector<std::vector<double>>& dist_mat, int n_components) {
            py::gil_scoped_release rel;
            return matrix_to_py(mds(py_to_matrix(dist_mat), n_components));
        },
        py::arg("dist_mat"), py::arg("n_components") = 2,
        "Classical MDS on a distance matrix. Returns list[list[float]] (n x n_components).");

    dr.def("tsne_affinities",
        [](const std::vector<std::vector<double>>& data, double perplexity) {
            py::gil_scoped_release rel;
            return matrix_to_py(tsne_affinities(py_to_matrix(data), perplexity));
        },
        py::arg("data"), py::arg("perplexity") = 30.0,
        "Compute symmetric t-SNE affinity matrix P from raw data. "
        "Returns list[list[float]] (n x n).");

    dr.def("geodesic_distances",
        [](const std::vector<std::vector<double>>& weights) {
            py::gil_scoped_release rel; return geodesic_distances(weights);
        },
        py::arg("weights"),
        "All-pairs shortest-path (geodesic) distances via Dijkstra. "
        "weights[i][j] > 0 is an edge; 0/negative means no edge. "
        "Returns n x n distance matrix; unreachable pairs get float('inf').");
}
