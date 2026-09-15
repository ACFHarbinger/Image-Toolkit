"""Tests for Track B Phase 2: ML model & loss-landscape scaffolding (#394).

All computations run on CPU against tiny toy models — the live models
(AnimeStitchNet, BiRefNet, LoFTR, DINOv2) are never imported here. Where an
exact analytic answer exists (identity Hessian from a pure quadratic loss)
the tests assert equality against it, not just shape/sanity.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from tool.model.loss_landscape import (  # noqa: E402
    ActivationAtlas,
    AttentionMap,
    EigenDensityBin,
    HessianSpectrum,
    LossSurface,
    TrajectoryPoint,
    TrajectoryProjection,
    resolve_model_adapter,
)
from tool.plugins.loss_landscape import MANIFEST, LossLandscapePlugin, plugin  # noqa: E402
from tool.research import loss_landscape as research  # noqa: E402


class ToyMLP(torch.nn.Module):
    """Tiny regression MLP for surface/trajectory tests."""

    def __init__(self, width: int = 8):
        super().__init__()
        self.hidden = torch.nn.Linear(4, width)
        self.out = torch.nn.Linear(width, 2)

    def forward(self, x):
        return self.out(torch.tanh(self.hidden(x)))


class ToyAttention(torch.nn.Module):
    """Emits a square 4D map from a named submodule (attention-shaped)."""

    def __init__(self):
        super().__init__()
        self.proj = torch.nn.Linear(4, 72)
        self.maps = torch.nn.Identity()

    def forward(self, x):
        h = torch.tanh(self.proj(x))
        grid = h.reshape(-1, 2, 6, 6)
        return self.maps(grid).sum(dim=(1, 2, 3))


@pytest.fixture()
def toy_batch():
    g = torch.Generator().manual_seed(0)
    x = torch.randn(8, 4, generator=g)
    y = torch.randn(8, 2, generator=g)
    return x, y


def _mse(model, batch):
    """Closure matching the research API's loss_fn(batch) contract."""

    def loss(_ignored=None):
        x, y = batch
        return torch.nn.functional.mse_loss(model(x), y)

    return loss


def _quadratic_loss(model):
    """Loss with identity Hessian: 0.5 * ||params||^2 (for exact checks)."""

    def loss(_ignored=None):
        return 0.5 * sum((p**2).sum() for p in model.parameters())

    return loss


class TestFilterNormalizationAndSurface:
    def test_directions_match_param_shapes_and_unit_norm(self):
        model = ToyMLP()
        dx, dy = research.filter_normalized_directions(model, seed=1)
        params = list(model.parameters())
        assert len(dx) == len(params) == len(dy)
        for d, p in zip(dx, params, strict=True):
            assert d.shape == p.shape
            if d.ndim >= 2:
                # Linear weights: per-output-channel norms == 1.
                flat = d.reshape(d.shape[0], -1)
                assert torch.allclose(flat.norm(dim=1), torch.ones(d.shape[0]), atol=1e-5)
            else:
                # Biases / norm gains: whole-tensor norm == 1.
                assert torch.allclose(d.norm(), torch.tensor(1.0), atol=1e-6)

    def test_surface_grid_shape_and_weight_restore(self, toy_batch):
        model = ToyMLP()
        before = [p.detach().clone() for p in model.parameters()]
        dx, dy = research.filter_normalized_directions(model, seed=2)
        surface = research.sample_loss_surface(
            model, _mse(model, toy_batch), toy_batch, dx, dy,
            alphas=[-1.0, 0.0, 1.0], betas=[-1.0, 0.0, 1.0],
            model_name="toy",
        )
        assert surface.resolution == (3, 3)
        assert np.isfinite(np.array(surface.losses)).all()
        assert surface.baseline_loss == pytest.approx(surface.losses[1][1])
        after = [p.detach().clone() for p in model.parameters()]
        for b, a in zip(before, after, strict=True):
            assert torch.equal(b, a)

    def test_optimizer_trajectory_records_points(self, toy_batch):
        model = ToyMLP()
        dx, dy = research.filter_normalized_directions(model, seed=3)
        points = research.project_optimizer_trajectory(
            model, _mse(model, toy_batch), toy_batch, dx, dy, optimize_steps=4, lr=0.05, log_every=2
        )
        assert len(points) == 2  # steps 2 and 4
        assert points[-1]["loss"] <= points[0]["loss"] + 1e-6
        for key in ("step", "alpha", "beta", "loss"):
            assert key in points[0]


class TestHessianGeometry:
    """Exact checks on a loss whose Hessian is the identity: H = I."""

    def test_hvp_is_identity(self):
        model = ToyMLP(width=4)
        v = [0.5, -1.0] + [0.25] * (sum(int(p.numel()) for p in model.parameters()) - 2)
        hvp = research.hessian_vector_product(model, _quadratic_loss(model), None, v)
        assert np.allclose(np.asarray(hvp), np.asarray(v), atol=1e-5)

    def test_hutchinson_trace_equals_numel(self):
        model = ToyMLP(width=4)
        numel = sum(int(p.numel()) for p in model.parameters())
        spectrum = research.hutchinson_trace(model, _quadratic_loss(model), None, num_probes=5, seed=0)
        assert spectrum.num_probes == 5
        assert spectrum.trace_estimate == pytest.approx(float(numel), rel=1e-5)

    def test_lanczos_density_collapses_to_identity(self):
        model = ToyMLP(width=4)
        spectrum = research.lanczos_spectral_density(
            model, _quadratic_loss(model), None,
            num_probes=3, lanczos_steps=8, density_bins=10, seed=0,
        )
        assert spectrum.trace_estimate == pytest.approx(
            float(sum(int(p.numel()) for p in model.parameters())), rel=1e-4
        )
        assert len(spectrum.density) == 1
        assert spectrum.density[0].center == pytest.approx(1.0, abs=1e-3)
        assert spectrum.density[0].weight == pytest.approx(1.0)
        assert spectrum.sharpness() == pytest.approx(1.0, abs=1e-3)


class TestTrajectoryProjection:
    def test_pca_explained_variance_for_linear_drift(self):
        rng = np.random.default_rng(0)
        base = rng.normal(size=16)
        direction = rng.normal(size=16)
        snapshots = [base + t * direction for t in range(6)]
        proj = research.project_trajectory(snapshots, steps=list(range(6)), method="pca", model_name="toy")
        assert isinstance(proj, TrajectoryProjection)
        assert len(proj.points) == 6
        assert all(len(p) == 2 for p in proj.points)
        # A straight-line drift is (numerically) rank-1: PC1 explains ~all.
        assert proj.explained_variance[0] > 0.99
        assert proj.norms_weight[-1] > proj.norms_weight[1]

    def test_tsne_runs_and_sizes_norms(self):
        rng = np.random.default_rng(1)
        snapshots = [rng.normal(size=24) * (1 + 0.1 * t) for t in range(8)]
        grads = [rng.normal(size=24) for _ in range(8)]
        proj = research.project_trajectory(
            snapshots, method="tsne", model_name="toy", grad_snapshots=grads, random_state=0
        )
        assert proj.method == "tsne"
        assert len(proj.points) == 8
        assert len(proj.norms_grad) == 8
        assert proj.explained_variance == []

    def test_too_few_snapshots_raises(self):
        with pytest.raises(ValueError):
            research.project_trajectory([np.zeros(4)], method="pca")

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            research.project_trajectory([np.zeros(4), np.ones(4)], method="umap")


class TestActivationCapture:
    def test_capture_linear_layer_atlas(self, toy_batch):
        model = ToyMLP()
        x, _y = toy_batch
        atlases = research.capture_activations(model, x, ["hidden"], model_name="toy")
        assert len(atlases) == 1
        atlas = atlases[0]
        assert isinstance(atlas, ActivationAtlas)
        assert atlas.model_name == "toy"
        assert atlas.spatial_shape == [8]  # width of ToyMLP.hidden
        assert len(atlas.embedding) == x.shape[0]
        assert len(atlas.channel_means) == x.shape[0]
        assert atlas.attention == []  # 2D output: no attention maps

    def test_capture_attention_shaped_layer(self):
        model = ToyAttention()
        x = torch.randn(4, 4)
        atlases = research.capture_activations(model, x, ["maps"], model_name="toy")
        assert len(atlases) == 1
        atlas = atlases[0]
        assert atlas.spatial_shape == [2, 6, 6]
        assert len(atlas.attention) >= 1
        amap = atlas.attention[0]
        assert isinstance(amap, AttentionMap)
        assert len(amap.grid) == 6  # below pool size: kept at native 6x6
        assert len(amap.grid[0]) == 6

    def test_unknown_layer_raises(self, toy_batch):
        model = ToyMLP()
        x, _y = toy_batch
        with pytest.raises(KeyError):
            research.capture_activations(model, x, ["nope"], model_name="toy")


class TestDataModelRoundTrips:
    def test_loss_surface_roundtrip(self):
        surface = LossSurface(
            model_name="toy",
            alpha_range=[-1.0, 0.0, 1.0],
            beta_range=[-1.0, 0.0, 1.0],
            losses=[[1.0, 0.5, 1.0], [0.5, 0.0, 0.5], [1.0, 0.5, 1.0]],
            trajectory=[TrajectoryPoint(step=0, alpha=0.0, beta=0.0, loss=0.1)],
        )
        restored = LossSurface.from_dict(surface.to_dict())
        assert restored.resolution == (3, 3)
        assert restored.trajectory[0].step == 0
        assert restored.min_loss() == 0.0 and restored.max_loss() == 1.0

    def test_hessian_spectrum_roundtrip(self):
        spec = HessianSpectrum(
            model_name="toy",
            trace_estimate=16.0,
            num_probes=5,
            lanczos_steps=8,
            density=[EigenDensityBin(center=1.0, weight=1.0)],
        )
        restored = HessianSpectrum.from_dict(spec.to_dict())
        assert restored.trace_estimate == 16.0
        assert restored.sharpness() == pytest.approx(1.0)
        assert restored.min_eigenvalue == 1.0

    def test_activation_atlas_roundtrip(self):
        atlas = ActivationAtlas(
            model_name="toy",
            layer_name="maps",
            spatial_shape=[2, 6, 6],
            embedding=[[0.0, 0.1], [0.2, 0.3]],
            channel_means=[[0.5] * 2] * 2,
            attention=[AttentionMap(layer_name="maps", head=-1, grid=[[0.1] * 6] * 6)],
        )
        restored = ActivationAtlas.from_dict(atlas.to_dict())
        assert restored.spatial_shape == [2, 6, 6]
        assert len(restored.attention) == 1
        assert len(restored.embedding) == 2


class TestPlugin:
    def test_manifest_fields(self):
        assert MANIFEST.name == "loss_landscape"
        assert "web" in MANIFEST.surface_names()
        assert "hessian_spectra" in MANIFEST.channel_keys()
        assert MANIFEST.effective_entry().python_module == "tool.plugins.loss_landscape:plugin"

    def test_artifact_discovery_and_summarize(self, tmp_path):
        export_dir = tmp_path / "dev" / "tool" / "export" / "loss_landscape"
        export_dir.mkdir(parents=True)
        surface = LossSurface(
            model_name="toy", alpha_range=[0.0], beta_range=[0.0], losses=[[0.25]]
        )
        spec = HessianSpectrum(
            model_name="toy", trace_estimate=4.0, num_probes=2,
            density=[EigenDensityBin(center=1.0, weight=1.0)],
        )
        traj = TrajectoryProjection(model_name="toy", method="pca", steps=[0, 1], points=[[0, 0], [1, 1]])
        (export_dir / "surface.json").write_text(json.dumps({"loss_surface": surface.to_dict()}))
        (export_dir / "spectrum.json").write_text(json.dumps({"hessian_spectrum": spec.to_dict()}))
        (export_dir / "traj.json").write_text(json.dumps({"weight_trajectory": traj.to_dict()}))
        (export_dir / "broken.json").write_text("not json")

        store = SimpleNamespace(repo_root=tmp_path)
        artifacts = plugin.artifacts(store)
        assert {a.name for a in artifacts} == {"surface.json", "spectrum.json", "traj.json"}
        by_name = {a.name: a for a in artifacts}
        assert by_name["surface.json"].meta["channel"] == "loss_surfaces"
        assert by_name["spectrum.json"].meta["channel"] == "hessian_spectra"

        summaries = {a.name: LossLandscapePlugin.summarize(a.path) for a in artifacts}
        assert summaries["surface.json"]["kind"] == "loss_surface"
        assert summaries["surface.json"]["grid"] == "1x1"
        assert summaries["spectrum.json"]["sharpness"] == pytest.approx(1.0)
        assert summaries["traj.json"]["steps"] == 2

    def test_no_export_dir_means_no_artifacts(self, tmp_path):
        assert plugin.artifacts(SimpleNamespace(repo_root=tmp_path)) == []


class TestModelAdapters:
    def test_unknown_model_returns_none(self):
        assert resolve_model_adapter("gpt-99") is None

    @pytest.mark.parametrize("name", ["animestitchnet", "birefnet", "loftr"])
    def test_adapter_lookup_is_lazy_and_safe(self, name):
        """Adapters resolve only when the underlying module imports; the
        function must not raise in any environment."""
        resolve_model_adapter(name)  # None when deps absent is fine — no exception.
