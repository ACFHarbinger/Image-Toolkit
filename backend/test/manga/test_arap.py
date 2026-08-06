import numpy as np
import pytest

from backend.src.manga.arap import arap_deform, generate_mesh


def _square_mask(h=100, w=100, margin=10):
    mask = np.zeros((h, w), dtype=bool)
    mask[margin : h - margin, margin : w - margin] = True
    return mask


class TestGenerateMesh:
    def test_returns_vertices_and_triangles(self):
        vertices, triangles = generate_mesh(_square_mask(), grid_step=10)
        assert vertices.ndim == 2 and vertices.shape[1] == 2
        assert triangles.ndim == 2 and triangles.shape[1] == 3

    def test_triangle_indices_are_in_range(self):
        vertices, triangles = generate_mesh(_square_mask(), grid_step=10)
        assert triangles.min() >= 0
        assert triangles.max() < vertices.shape[0]

    def test_every_vertex_is_referenced_by_a_triangle(self):
        """generate_mesh drops unreferenced vertices -- a vertex with no
        incident triangle would leave a structurally zero Laplacian row,
        which splu can't factor."""
        vertices, triangles = generate_mesh(_square_mask(), grid_step=10)
        used = np.unique(triangles)
        assert len(used) == vertices.shape[0]

    def test_finer_grid_step_produces_more_vertices(self):
        v_coarse, _ = generate_mesh(_square_mask(), grid_step=20)
        v_fine, _ = generate_mesh(_square_mask(), grid_step=5)
        assert v_fine.shape[0] > v_coarse.shape[0]

    def test_too_few_grid_points_raises(self):
        tiny_mask = np.zeros((20, 20), dtype=bool)
        tiny_mask[5:8, 5:8] = True
        with pytest.raises(ValueError, match="too few grid points"):
            generate_mesh(tiny_mask, grid_step=50)

    def test_vertices_stay_within_mask_bounding_region(self):
        mask = _square_mask(h=100, w=100, margin=10)
        vertices, _ = generate_mesh(mask, grid_step=10)
        assert vertices[:, 0].min() >= 10
        assert vertices[:, 0].max() <= 89
        assert vertices[:, 1].min() >= 10
        assert vertices[:, 1].max() <= 89


class TestArapDeform:
    def test_identity_anchors_leave_mesh_unchanged(self):
        vertices, triangles = generate_mesh(_square_mask(), grid_step=10)
        anchors = {i: tuple(vertices[i]) for i in range(0, vertices.shape[0], 4)}

        q = arap_deform(vertices, triangles, anchors, n_iters=5)
        assert np.allclose(q, vertices, atol=1e-6)

    def test_output_shape_matches_input(self):
        vertices, triangles = generate_mesh(_square_mask(), grid_step=10)
        anchors = {0: tuple(vertices[0] + [5, 0])}
        q = arap_deform(vertices, triangles, anchors)
        assert q.shape == vertices.shape

    def test_anchor_positions_are_pinned_exactly(self):
        vertices, triangles = generate_mesh(_square_mask(), grid_step=10)
        target = (vertices[0, 0] + 12.0, vertices[0, 1] - 4.0)
        q = arap_deform(vertices, triangles, {0: target}, n_iters=8)
        assert np.allclose(q[0], target, atol=1e-9)

    def test_full_boundary_rigid_rotation_is_reproduced_by_free_vertices(self):
        """The core ARAP correctness check: if every boundary vertex is
        anchored to a rigidly-rotated position, the free interior vertices
        should converge to their own rigidly-rotated positions too -- ARAP's
        whole point is exactly reproducing rigid motion when nothing
        contradicts it."""
        vertices, triangles = generate_mesh(_square_mask(h=120, w=120, margin=10), grid_step=15)
        center = vertices.mean(axis=0)
        theta = np.deg2rad(20)
        rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])

        def rotate(pts):
            return (pts - center) @ rot.T + center

        xs, ys = vertices[:, 0], vertices[:, 1]
        boundary = (xs == xs.min()) | (xs == xs.max()) | (ys == ys.min()) | (ys == ys.max())
        boundary_idx = np.where(boundary)[0]

        rotated_all = rotate(vertices)
        anchors = {int(i): tuple(rotated_all[i]) for i in boundary_idx}

        q = arap_deform(vertices, triangles, anchors, n_iters=10)

        free_mask = np.ones(vertices.shape[0], dtype=bool)
        free_mask[boundary_idx] = False
        err = np.linalg.norm(q[free_mask] - rotated_all[free_mask], axis=1)
        mesh_scale = np.linalg.norm(vertices.max(axis=0) - vertices.min(axis=0))
        # Well under 1% of the mesh's own scale -- a real correctness bound,
        # not just "didn't crash".
        assert err.max() < 0.01 * mesh_scale

    def test_single_anchor_displacement_stays_finite_and_decays_with_distance(self):
        vertices, triangles = generate_mesh(_square_mask(h=120, w=120, margin=10), grid_step=10)
        anchor_idx = 0
        target = tuple(vertices[anchor_idx] + [20, 0])

        q = arap_deform(vertices, triangles, {anchor_idx: target}, n_iters=10)
        assert np.isfinite(q).all()

        displacement = np.linalg.norm(q - vertices, axis=1)
        distance_from_anchor = np.linalg.norm(vertices - vertices[anchor_idx], axis=1)
        # Farther vertices should generally be displaced less than the
        # anchor itself (local rigidity means the pull attenuates).
        assert displacement.max() == pytest.approx(displacement[anchor_idx], abs=1e-6)
        assert displacement[distance_from_anchor.argmax()] < displacement[anchor_idx]

    def test_no_anchors_raises(self):
        vertices, triangles = generate_mesh(_square_mask(), grid_step=10)
        with pytest.raises(ValueError, match="at least one anchor"):
            arap_deform(vertices, triangles, {})

    def test_out_of_range_anchor_index_raises(self):
        vertices, triangles = generate_mesh(_square_mask(), grid_step=10)
        with pytest.raises(ValueError, match="out of range"):
            arap_deform(vertices, triangles, {vertices.shape[0] + 100: (0.0, 0.0)})

    def test_more_iterations_do_not_diverge(self):
        vertices, triangles = generate_mesh(_square_mask(), grid_step=15)
        anchors = {0: tuple(vertices[0] + [10, 5])}
        q_few = arap_deform(vertices, triangles, anchors, n_iters=2)
        q_many = arap_deform(vertices, triangles, anchors, n_iters=15)
        assert np.isfinite(q_few).all()
        assert np.isfinite(q_many).all()
        # Should converge, not blow up -- later iterations shouldn't be
        # wildly different in scale from earlier ones.
        assert np.linalg.norm(q_many - vertices) < 10 * np.linalg.norm(q_few - vertices) + 1.0
