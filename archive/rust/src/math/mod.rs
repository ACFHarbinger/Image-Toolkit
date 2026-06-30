//! Analytics and interpretability math backbone.
//!
//! Sub-modules provide the primitives consumed by the analytics_and_interpretability
//! roadmap phases:
//!
//! | Module        | Phases                                      |
//! |---------------|---------------------------------------------|
//! | `linalg`      | 1.3 (PCA layout), 2 (weight spaces), 10     |
//! | `stats`       | 4 (failure clustering), 2.3 (gradients)     |
//! | `information` | 4.1 (dependency entropy), 1.3 (LSI)         |
//! | `distance`    | 1.3 (MDS stress), 4.4 (DBSCAN), 10 (TDA)   |
//! | `graph`       | 1 (AST/dep graph), 4.2 (causal DAG), 10    |
//! | `dim_reduce`  | 1.3 (MDS/Isomap), t-SNE affinities          |

pub mod dim_reduce;
pub mod distance;
pub mod graph;
pub mod information;
pub mod linalg;
pub mod stats;

// Re-export the most commonly used types and functions for ergonomic imports.
pub use dim_reduce::{geodesic_distances, mds_project, tsne_affinities};
pub use distance::{
    condensed_distance_matrix, cosine_distance, cosine_similarity, euclidean,
    hellinger_distance, manhattan, pairwise_distance_matrix,
};
pub use graph::{
    Graph, UnionFind, bfs, connected_components, dfs, kruskal_max_mst, kruskal_mst,
    strongly_connected_components, topological_sort,
};
pub use information::{
    js_divergence, kl_divergence, mutual_information_discrete, normalised_mutual_information,
    shannon_entropy,
};
pub use linalg::{Matrix, dot, norm, normalize, pca_2d, pca_project};
pub use stats::{
    histogram, mean, median, min_max_normalize, pearson_correlation, percentile, std_dev,
    variance, z_score_normalize,
};
