"""Loss-landscape computations for Track B Phase 2 (issue #394).

Pure PyTorch/numpy/scipy implementations of the Phase 2 spec's algorithms.
The spec names ``loss-landscapes`` and ``PyHessian``; neither is a project
dependency, so the core methods are implemented here directly (they are
compact) and no new deps are added. Everything operates on a model + loss
function + one batch; the heavy live models (AnimeStitchNet, BiRefNet,
LoFTR, DINOv2) are exercised through :func:`resolve_model_adapter` only in
environments that have them — tests use a tiny CPU toy model.

- :func:`filter_normalized_directions` / :func:`sample_loss_surface` —
  Li et al. (2018) filter normalization + 2D surface sampling (§2.1).
- :func:`hessian_vector_product` / :func:`hutchinson_trace` /
  :func:`lanczos_spectral_density` — Hutchinson trace + Stochastic Lanczos
  Quadrature ESD (§2.2), the PyHessian algorithms re-implemented.
- :func:`project_trajectory` — PCA / t-SNE projection of weight or gradient
  snapshots (§2.3).
- :func:`capture_activations` — forward-hook activation capture reduced to
  an atlas embedding, plus pooled attention maps (§2.4/§2.5).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..model.loss_landscape import (
    ActivationAtlas,
    AttentionMap,
    EigenDensityBin,
    HessianSpectrum,
    LossSurface,
    TrajectoryProjection,
)

FilterLike = Any  # torch.nn.Module, imported lazily to keep import cheap
LossFn = Callable[[Any], Any]

_ATTENTION_POOL = 14  # native attention maps are pooled to this grid size


def _torch():
    import torch

    return torch


# ---------------------------------------------------------------------------
# 2.1 Filter normalization + loss-surface sampling
# ---------------------------------------------------------------------------


def filter_normalized_directions(model: FilterLike, seed: int = 0) -> Tuple[List[Any], List[Any]]:
    """Two filter-normalized random directions shaped like ``model`` params.

    Li et al. (2018): a raw Gaussian direction is misleading near
    normalization layers because parameter scales vary wildly across layers.
    Each filter (output channel for >=2D tensors, whole tensor for biases /
    norm gains) is rescaled to unit norm, so one unit of alpha/beta moves
    every filter by a comparable amount. Returns ``(dir_x, dir_y)`` as
    tensors matching the model's parameters.
    """
    torch = _torch()
    rng = torch.Generator().manual_seed(seed)
    dirs: List[List[Any]] = [[], []]
    for param in model.parameters():
        for out in dirs:
            d = torch.randn(param.shape, generator=rng, dtype=param.dtype)
            if d.ndim >= 2:
                # normalize per output channel (filter), like the paper
                flat = d.reshape(d.shape[0], -1)
                norms = flat.norm(dim=1, keepdim=True).clamp_min(1e-12)
                d = (flat / norms).reshape(d.shape)
            else:
                d = d / d.norm().clamp_min(1e-12)
            out.append(d.to(dtype=param.dtype))
    return dirs[0], dirs[1]


def _flatten_params(model: FilterLike) -> Tuple[List[Any], List[int], List[Any]]:
    """Snapshot parameter tensors: values, original shapes, references."""
    refs = [p for p in model.parameters()]
    shapes = [tuple(p.shape) for p in refs]
    return [p.detach().clone() for p in refs], shapes, refs


def _set_params(refs: Sequence[Any], base: Sequence[Any], dx: Optional[Sequence[Any]],
                dy: Optional[Sequence[Any]], alpha: float, beta: float) -> None:
    for i, p in enumerate(refs):
        value = base[i]
        if dx is not None:
            value = value + alpha * dx[i]
        if dy is not None:
            value = value + beta * dy[i]
        p.data.copy_(value.to(p.dtype))


def sample_loss_surface(
    model: FilterLike,
    loss_fn: LossFn,
    batch: Any,
    dir_x: Sequence[Any],
    dir_y: Sequence[Any],
    alphas: Sequence[float],
    betas: Sequence[float],
    model_name: str = "model",
) -> LossSurface:
    """Evaluate ``loss`` on the filter-normalized grid around current weights.

    Restores the original weights on exit (also on error). ``alphas`` are
    sampled along ``dir_x``, ``betas`` along ``dir_y``; ``losses[row][col]``
    is the loss at ``(alpha=alphas[col], beta=betas[row])``.
    """
    torch = _torch()
    base, _shapes, refs = _flatten_params(model)
    losses: List[List[float]] = []
    was_training = model.training
    model.eval()
    try:
        with torch.no_grad():
            for beta in betas:
                row: List[float] = []
                for alpha in alphas:
                    _set_params(refs, base, dir_x, dir_y, alpha, beta)
                    row.append(float(loss_fn(batch)))
                losses.append(row)
    finally:
        for p, b in zip(refs, base, strict=True):
            p.data.copy_(b.to(p.dtype))
        if was_training:
            model.train()
    return LossSurface(
        model_name=model_name,
        alpha_range=[float(a) for a in alphas],
        beta_range=[float(b) for b in betas],
        losses=losses,
        baseline_loss=losses[len(betas) // 2][len(alphas) // 2] if losses else 0.0,
    )


def project_optimizer_trajectory(
    model: FilterLike,
    loss_fn: LossFn,
    batch: Any,
    dir_x: Sequence[Any],
    dir_y: Sequence[Any],
    optimize_steps: int,
    lr: float = 1e-2,
    log_every: int = 1,
    model_name: str = "model",
) -> List[Dict[str, float]]:
    """Run a short optimization from the current weights and record the path
    projected onto the two surface directions.

    Returns trajectory points (alpha, beta, loss) usable as the
    ``LossSurface.trajectory`` overlay — §2.1's "optimizer trajectory across
    the non-convex loss surface". Uses AdamW; runs ``optimize_steps`` SGD
    steps, logging every ``log_every`` steps.
    """
    torch = _torch()
    base, _shapes, refs = _flatten_params(model)
    opt = torch.optim.AdamW(refs, lr=lr)
    points: List[Dict[str, float]] = []

    def _project() -> Tuple[float, float]:
        flat_d = [d.reshape(-1).float() for d in dir_x]
        flat_e = [d.reshape(-1).float() for d in dir_y]
        total_d = torch.cat(flat_d)
        total_e = torch.cat(flat_e)
        diff = torch.cat([(p.detach().reshape(-1) - b.reshape(-1).to(p.dtype)).float() for p, b in zip(refs, base, strict=True)])
        denom_d = (total_d * total_d).sum().clamp_min(1e-12)
        denom_e = (total_e * total_e).sum().clamp_min(1e-12)
        alpha = float((diff * total_d).sum() / denom_d)
        beta = float((diff * total_e).sum() / denom_e)
        return alpha, beta

    was_training = model.training
    model.train()
    try:
        for step in range(1, optimize_steps + 1):
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(batch)
            loss.backward()
            opt.step()
            if step % max(1, log_every) == 0 or step == optimize_steps:
                alpha, beta = _project()
                points.append({"step": step, "alpha": alpha, "beta": beta, "loss": float(loss.detach())})
    finally:
        if was_training is False:
            model.eval()
    return points


# ---------------------------------------------------------------------------
# 2.2 Hessian geometry: Hutchinson trace + SLQ spectral density
# ---------------------------------------------------------------------------


def hessian_vector_product(model: FilterLike, loss_fn: LossFn, batch: Any, v: Sequence[float]) -> List[float]:
    """H * v for the Hessian of ``loss_fn`` at the model's current weights,
    via autograd double-backpropagation (Pearlmutter trick equivalent).
    """
    torch = _torch()
    params = [p for p in model.parameters()]
    loss = loss_fn(batch)
    grads = torch.autograd.grad(loss, params, create_graph=True)
    flat_grads = torch.cat([g.reshape(-1).float() for g in grads])
    v_t = torch.as_tensor(v, dtype=flat_grads.dtype, device=flat_grads.device)
    hvp = torch.autograd.grad(flat_grads @ v_t, params, retain_graph=False)
    return [float(x) for x in torch.cat([h.reshape(-1) for h in hvp]).detach()]


def hutchinson_trace(
    model: FilterLike,
    loss_fn: LossFn,
    batch: Any,
    num_probes: int = 20,
    seed: int = 0,
    model_name: str = "model",
) -> HessianSpectrum:
    """Estimate ``Tr(H)`` via Hutchinson's estimator: for Rademacher probes
    ``z`` (±1 entries), ``E[z^T H z] = Tr(H)``. No eigenvalues here — pair
    with :func:`lanczos_spectral_density` for the full spectrum.
    """
    rng = np.random.default_rng(seed)
    numel = sum(int(np.prod(tuple(p.shape))) for p in model.parameters())
    traces: List[float] = []
    for _ in range(num_probes):
        z = rng.choice([-1.0, 1.0], size=numel)
        hvp = hessian_vector_product(model, loss_fn, batch, z)
        traces.append(float(np.dot(z, hvp)))
    return HessianSpectrum(
        model_name=model_name,
        trace_estimate=float(np.mean(traces)),
        num_probes=num_probes,
    )


def _lanczos_tridiagonal(hvp: Callable[[np.ndarray], np.ndarray], q0: np.ndarray, steps: int) -> Tuple[np.ndarray, np.ndarray]:
    """Plain Lanczos: returns (alphas, betas) of the tridiagonal T."""
    alphas = np.zeros(steps)
    betas = np.zeros(steps - 1)
    q = q0 / np.linalg.norm(q0)
    q_prev = np.zeros_like(q)
    beta_prev = 0.0
    for j in range(steps):
        z = hvp(q) - beta_prev * q_prev
        alpha = float(q @ z)
        alphas[j] = alpha
        z = z - alpha * q
        if j < steps - 1:
            beta = float(np.linalg.norm(z))
            betas[j] = beta
            if beta < 1e-10:
                return alphas[: j + 1], betas[:j]
            q_prev, q = q, z / beta
            beta_prev = beta
    return alphas, betas


def _tridiag_eigs(alphas: np.ndarray, betas: np.ndarray) -> np.ndarray:
    t = np.diag(alphas)
    if len(betas):
        off = np.diag(betas)
        t += off + off.T
    return np.linalg.eigvalsh(t)


def lanczos_spectral_density(
    model: FilterLike,
    loss_fn: LossFn,
    batch: Any,
    num_probes: int = 10,
    lanczos_steps: int = 20,
    density_bins: int = 40,
    seed: int = 0,
    model_name: str = "model",
) -> HessianSpectrum:
    """Eigenvalue spectral density via Stochastic Lanczos Quadrature.

    Each Rademacher probe seeds a Lanczos run whose Ritz values (eigenvalues
    of the small tridiagonal) approximate extremal Hessian eigenvalues; the
    ESD is the equal-weight mixture over probes. Sharp minima show a large
    right-edge eigenvalue; flat minima show density concentrated near zero.
    """
    rng = np.random.default_rng(seed)
    numel = sum(int(np.prod(tuple(p.shape))) for p in model.parameters())

    def hvp(q: np.ndarray) -> np.ndarray:
        return np.asarray(hessian_vector_product(model, loss_fn, batch, q), dtype=np.float64)

    ritz: List[float] = []
    trace_acc = 0.0
    for _ in range(num_probes):
        z = rng.choice([-1.0, 1.0], size=numel).astype(np.float64)
        trace_acc += float(z @ hvp(z))
        alphas, betas = _lanczos_tridiagonal(hvp, z, min(lanczos_steps, numel))
        ritz.extend(_tridiag_eigs(alphas, betas).tolist())

    if not ritz:
        return HessianSpectrum(model_name=model_name, num_probes=num_probes, lanczos_steps=lanczos_steps)

    lo, hi = min(ritz), max(ritz)
    if hi - lo < 1e-12:
        bins = [EigenDensityBin(center=lo, weight=1.0)]
    else:
        counts, edges = np.histogram(ritz, bins=density_bins)
        total = float(counts.sum())
        bins = [
            EigenDensityBin(center=float((edges[i] + edges[i + 1]) / 2.0), weight=float(counts[i]) / total)
            for i in range(len(counts))
            if counts[i] > 0
        ]
    return HessianSpectrum(
        model_name=model_name,
        trace_estimate=trace_acc / num_probes,
        num_probes=num_probes,
        lanczos_steps=lanczos_steps,
        density=bins,
    )


# ---------------------------------------------------------------------------
# 2.3 Weight / gradient trajectory projection
# ---------------------------------------------------------------------------


def project_trajectory(
    snapshots: Sequence[np.ndarray],
    steps: Optional[Sequence[int]] = None,
    method: str = "pca",
    model_name: str = "model",
    grad_snapshots: Optional[Sequence[np.ndarray]] = None,
    random_state: int = 0,
) -> TrajectoryProjection:
    """Project a series of weight (or gradient) vectors to 2D.

    ``snapshots[i]`` is a flat vector for epoch/step ``i``; the first
    snapshot is treated as the origin (distances are from-init). ``pca``
    keeps explained-variance ratios; ``tsne`` is nonlinear (no explained
    variance — norms carry the magnitude story). ``grad_snapshots``, when
    given, supplies per-step gradient norms for point sizing.
    """
    if len(snapshots) < 2:
        raise ValueError("need at least two snapshots to project a trajectory")
    x = np.stack([np.asarray(s, dtype=np.float64).reshape(-1) for s in snapshots])
    origin = x[0]
    delta = x - origin
    norms_weight = [float(np.linalg.norm(d)) for d in delta]
    norms_grad = (
        [float(np.linalg.norm(np.asarray(g, dtype=np.float64).reshape(-1))) for g in grad_snapshots]
        if grad_snapshots is not None
        else []
    )
    step_list = [int(s) for s in steps] if steps is not None else list(range(len(snapshots)))

    method = method.lower()
    if method == "pca":
        _center = delta - delta.mean(axis=0, keepdims=True)
        _u, _s, vt = np.linalg.svd(_center, full_matrices=False)
        comps = vt[:2]
        points = (delta @ comps.T).tolist()
        total_var = float((_s ** 2).sum()) or 1.0
        explained = [float((_s[i] ** 2) / total_var) for i in range(min(2, len(_s)))]
    elif method == "tsne":
        from sklearn.manifold import TSNE

        perplexity = max(1, min(30, len(snapshots) - 1))
        points = TSNE(n_components=2, random_state=random_state, perplexity=perplexity).fit_transform(delta).tolist()
        explained = []
    else:
        raise ValueError(f"unknown method {method!r}; expected 'pca' or 'tsne'")

    return TrajectoryProjection(
        model_name=model_name,
        method=method,
        steps=step_list,
        points=[[round(float(v), 6) for v in p] for p in points],
        explained_variance=[round(v, 6) for v in explained],
        norms_weight=[round(v, 6) for v in norms_weight],
        norms_grad=[round(v, 6) for v in norms_grad],
    )


# ---------------------------------------------------------------------------
# 2.4 / 2.5 Activation capture + attention maps
# ---------------------------------------------------------------------------


def _pool_grid(values: np.ndarray, size: int) -> List[List[float]]:
    """Average-pool a 2D array to ``size`` x ``size`` (crop if smaller)."""
    if values.shape[0] < size or values.shape[1] < size:
        return values.astype(float).round(6).tolist()
    h, w = values.shape
    ph, pw = h // size, w // size
    pooled = values[: ph * size, : pw * size].reshape(size, ph, size, pw).mean(axis=(1, 3))
    return pooled.astype(float).round(6).tolist()


def capture_activations(
    model: FilterLike,
    batch: Any,
    layer_names: Sequence[str],
    model_name: str = "model",
    max_samples: int = 512,
    seed: int = 0,
) -> List[ActivationAtlas]:
    """Capture named layer outputs during one forward pass.

    For each requested layer: flatten each sample's activations, subsample
    up to ``max_samples``, embed them to 2D via PCA, and record per-channel
    means (reconstructable tiles for the atlas view). Outputs that look like
    attention maps (4D, square last two dims, values in [0, 1] after softmax
    or [0, inf)) are additionally pooled to :data:`_ATTENTION_POOL` grids for
    the overlay heatmaps of §2.5.
    """
    torch = _torch()
    rng = np.random.default_rng(seed)
    modules = dict(model.named_modules())
    captured: Dict[str, List[np.ndarray]] = {name: [] for name in layer_names}
    hooks = []

    def _make_hook(name: str):
        def _hook(_module, _inputs, output):
            tensor = output[0] if isinstance(output, (tuple, list)) else output
            if hasattr(tensor, "detach"):
                captured[name].append(tensor.detach().float().cpu().numpy())

        return _hook

    was_training = model.training
    model.eval()
    try:
        for name in layer_names:
            if name not in modules:
                raise KeyError(f"layer {name!r} not found on model")
            hooks.append(modules[name].register_forward_hook(_make_hook(name)))
        with torch.no_grad():
            model(batch)
    finally:
        for h in hooks:
            h.remove()
        if was_training:
            model.train()

    atlases: List[ActivationAtlas] = []
    for name in layer_names:
        arrays = captured[name]
        if not arrays:
            continue
        arr = np.concatenate(arrays, axis=0)  # [N, C, ...]
        spatial = list(arr.shape[1:])
        flat = arr.reshape(arr.shape[0], -1)
        if flat.shape[0] > max_samples:
            idx = rng.choice(flat.shape[0], size=max_samples, replace=False)
            flat = flat[idx]
        channel_means = arr.reshape(arr.shape[0], arr.shape[1], -1).mean(axis=2)
        if flat.shape[0] >= 2:
            centered = flat - flat.mean(axis=0, keepdims=True)
            _u, _s, vt = np.linalg.svd(centered, full_matrices=False)
            embedding = (centered @ vt[:2].T).round(6).tolist()
        else:
            embedding = [[0.0, 0.0] for _ in range(flat.shape[0])]

        attention: List[AttentionMap] = []
        if arr.ndim == 4 and arr.shape[-1] == arr.shape[-2]:
            heads = arr.shape[1] if arr.shape[1] <= 16 else 1
            for h_idx in range(min(heads, 4)):  # cap stored heads
                pooled = _pool_grid(arr[0, h_idx] if heads > 1 else arr[0, 0], _ATTENTION_POOL)
                attention.append(AttentionMap(layer_name=name, head=h_idx if heads > 1 else -1, grid=pooled))

        atlases.append(
            ActivationAtlas(
                model_name=model_name,
                layer_name=name,
                spatial_shape=spatial,
                embedding=embedding,
                channel_means=channel_means.round(6).tolist(),
                sample_ids=[f"{name}:{i}" for i in range(flat.shape[0])],
                attention=attention,
            )
        )
    return atlases


__all__ = [
    "capture_activations",
    "filter_normalized_directions",
    "hessian_vector_product",
    "hutchinson_trace",
    "lanczos_spectral_density",
    "project_optimizer_trajectory",
    "project_trajectory",
    "sample_loss_surface",
]
