/// @file test_solvers.cpp
/// @brief Unit tests for exact_solvers and metaheuristics.

#include <cassert>
#include <cmath>
#include <cstdio>
#include <vector>

#include "exact_solvers.hpp"
#include "metaheuristics.hpp"
#include "render_graph.hpp"

using namespace hybrid_image_editor;

// ─── Seam Routing Tests ───────────────────────────────────────────────────────

static void test_seam_basic() {
    // 3×3 grid — seam should prefer the zero-energy column (col 1)
    std::vector<SeamPixel> grid = {
        {1.f, false}, {0.f, false}, {1.f, false},
        {1.f, false}, {0.f, false}, {1.f, false},
        {1.f, false}, {0.f, false}, {1.f, false},
    };
    SeamResult r = solve_seam(grid, 3, 3);
    assert(r.success);
    for (int x : r.seam_x) {
        assert(x == 1 && "Seam should follow the zero-energy column");
    }
    std::printf("[PASS] test_seam_basic\n");
}

static void test_seam_masked_barrier() {
    // 3×3: mask column 1 at row 1 — seam must go around it
    std::vector<SeamPixel> grid = {
        {0.f, false}, {0.f, false}, {0.f, false},
        {1.f, false}, {1.f, true},  {1.f, false},  // col 1 masked
        {0.f, false}, {0.f, false}, {0.f, false},
    };
    SeamResult r = solve_seam(grid, 3, 3);
    assert(r.success);
    // Row 1 seam must NOT be at column 1 (masked)
    assert(r.seam_x[1] != 1 && "Seam must avoid masked character pixel");
    std::printf("[PASS] test_seam_masked_barrier\n");
}

// ─── GNC-TLS Alignment Tests ──────────────────────────────────────────────────

static void test_alignment_pure_translation() {
    // Pure translation: tx=10, ty=-5, scale=1
    std::vector<Correspondence> corrs;
    for (int i = 0; i < 10; ++i) {
        Correspondence c;
        c.src_x = static_cast<float>(i * 20);
        c.src_y = static_cast<float>(i * 10);
        c.dst_x = c.src_x + 10.f;
        c.dst_y = c.src_y - 5.f;
        corrs.push_back(c);
    }
    AlignmentResult r = solve_alignment_gnc(corrs);
    assert(r.success);
    assert(std::abs(r.model.scale - 1.f) < 0.05f && "Scale should be ~1");
    assert(std::abs(r.model.tx - 10.f) < 1.f     && "tx should be ~10");
    assert(std::abs(r.model.ty - (-5.f)) < 1.f   && "ty should be ~-5");
    std::printf("[PASS] test_alignment_pure_translation (tx=%.2f ty=%.2f s=%.4f)\n",
                r.model.tx, r.model.ty, r.model.scale);
}

static void test_alignment_with_outliers() {
    std::vector<Correspondence> corrs;
    for (int i = 0; i < 20; ++i) {
        Correspondence c;
        c.src_x = static_cast<float>(i * 15);
        c.src_y = static_cast<float>(i * 8);
        c.dst_x = c.src_x * 1.1f + 5.f;
        c.dst_y = c.src_y * 1.1f + 3.f;
        corrs.push_back(c);
    }
    // Add 4 gross outliers
    for (int i = 0; i < 4; ++i) {
        Correspondence c{100.f * i, 50.f * i, 9999.f, -9999.f};
        corrs.push_back(c);
    }
    AlignmentResult r = solve_alignment_gnc(corrs, 12, 5.f);
    assert(r.success);
    assert(r.inlier_count >= 18 && "GNC should reject the 4 outliers");
    std::printf("[PASS] test_alignment_with_outliers (inliers=%u)\n", r.inlier_count);
}

// ─── Color Harmonization Tests ────────────────────────────────────────────────

static void test_color_harmonization_identity() {
    LayerColorStats src{50.f, 0.f, 0.f, 20.f, 5.f, 5.f};
    LayerColorStats tgt{50.f, 0.f, 0.f, 20.f, 5.f, 5.f};
    auto r = solve_color_harmonization(src, tgt);
    assert(r.success);
    assert(std::abs(r.alpha_l - 1.f) < 1e-4f);
    assert(std::abs(r.beta_l)        < 1e-4f);
    std::printf("[PASS] test_color_harmonization_identity\n");
}

// ─── PSO Tests ────────────────────────────────────────────────────────────────

static void test_pso_sphere() {
    // Minimise f(x) = x[0]^2 + x[1]^2 (minimum at 0,0)
    auto obj = [](const std::vector<float>& x) {
        return x[0] * x[0] + x[1] * x[1];
    };
    std::vector<ParamBound> bounds = {{-10.f, 10.f}, {-10.f, 10.f}};
    PSOConfig cfg;
    cfg.n_particles = 20;
    cfg.max_iter    = 200;
    auto r = pso_solve(obj, bounds, cfg);
    assert(r.best_fitness < 0.1f && "PSO should find near-zero minimum");
    std::printf("[PASS] test_pso_sphere (fitness=%.6f)\n", r.best_fitness);
}

// ─── DE Tests ─────────────────────────────────────────────────────────────────

static void test_de_rosenbrock() {
    // Rosenbrock: f(x,y) = (1-x)^2 + 100*(y-x^2)^2. Minimum at (1,1).
    auto obj = [](const std::vector<float>& x) {
        float a = 1.f - x[0];
        float b = x[1] - x[0] * x[0];
        return a * a + 100.f * b * b;
    };
    std::vector<ParamBound> bounds = {{-2.f, 2.f}, {-2.f, 2.f}};
    DEConfig cfg;
    cfg.popsize  = 20;
    cfg.max_iter = 500;
    auto r = de_solve(obj, bounds, cfg);
    assert(r.best_fitness < 0.5f && "DE should converge near Rosenbrock minimum");
    std::printf("[PASS] test_de_rosenbrock (fitness=%.6f)\n", r.best_fitness);
}

// ─── Render Graph Tests ───────────────────────────────────────────────────────

static void test_render_graph_topo_order() {
    Document doc;
    doc.document_id = "test-doc";

    Layer layer;
    layer.id   = "layer-0";
    layer.name = "Base";

    ModifierNode n1; n1.id = "node-A"; n1.type = "matting";
    ModifierNode n2; n2.id = "node-B"; n2.type = "superres";
    layer.modifiers = {n1, n2};
    doc.layers.push_back(layer);

    ModifierEdge edge; edge.source = "node-A"; edge.target = "node-B";
    doc.modifier_edges.push_back(edge);

    RenderGraph graph;
    graph.build(doc);

    auto order = graph.topological_order();
    assert(order.size() == 2);
    assert(order[0] == "node-A");
    assert(order[1] == "node-B");

    std::printf("[PASS] test_render_graph_topo_order\n");
}

static void test_render_graph_evaluate() {
    Document doc;
    doc.document_id = "test-doc-2";

    // Add one frame so evaluation can proceed
    Frame f; f.index = 0; f.asset_id = "asset-1"; f.timestamp_ms = 0.0;
    doc.frame_sequence.frames.push_back(f);

    Layer layer;
    layer.id = "layer-0";
    ModifierNode node; node.id = "node-X"; node.type = "curve";
    layer.modifiers = {node};
    doc.layers.push_back(layer);

    RenderGraph graph;
    graph.build(doc);

    int tile_count = 0;
    graph.evaluate(0, [&](const RenderTile&, const std::string&) {
        ++tile_count;
    });

    assert(tile_count > 0 && "Should emit at least one tile on first evaluation");
    assert(graph.is_clean()  && "Graph should be clean after full evaluation");

    // Second evaluation: no dirty tiles → no callbacks
    int second_count = 0;
    graph.evaluate(0, [&](const RenderTile&, const std::string&) { ++second_count; });
    assert(second_count == 0 && "Second evaluation should skip cache-valid nodes");

    std::printf("[PASS] test_render_graph_evaluate\n");
}

// ─── Main ─────────────────────────────────────────────────────────────────────

int main() {
    std::printf("=== HIE Solver Unit Tests ===\n");

    test_seam_basic();
    test_seam_masked_barrier();
    test_alignment_pure_translation();
    test_alignment_with_outliers();
    test_color_harmonization_identity();
    test_pso_sphere();
    test_de_rosenbrock();
    test_render_graph_topo_order();
    test_render_graph_evaluate();

    std::printf("=== All tests passed ===\n");
    return 0;
}
