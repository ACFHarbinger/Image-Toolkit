"""Real-ESRGAN anime-6B through the existing RRDBNet wrapper.

The other family ids are registered so the Sampler can list them. Their checkpoints
are not loaded by ``ESRGANWrapper`` (it always fetches the anime-6B file), so they
report that reason instead of running the wrong network.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from middleware.src.services.media.gif_upscale.base import AlgorithmError, AlgorithmSpec
from middleware.src.services.media.gif_upscale.policy import cache_dir, weights_policy
from middleware.src.services.media.gif_upscale.registry import register_algorithm

_ANIME_FILE = "RealESRGAN_x4plus_anime_6B.pth"
_UNWIRED = (
    ("realesrgan-x4plus", "RealESRGAN_x4plus is a 23-block RRDBNet and is not the anime-6B checkpoint this wrapper loads."),
    ("realesrgan-x2plus", "RealESRGAN_x2plus is a 2x network. The in-repo RRDBNet is 4x only."),
    ("realesrgan-general-x4v3", "realesr-general-x4v3 is an SRVGGNetCompact checkpoint, not the in-repo RRDBNet."),
    ("realesrgan-animevideov3", "realesr-animevideov3 is an SRVGGNetCompact checkpoint, not the in-repo RRDBNet."),
)


def _local_checkpoint() -> str | None:
    """A weight file already on disk. The GIF cache wins over the Hugging Face cache."""
    cached = cache_dir() / _ANIME_FILE
    if cached.is_file():
        return str(cached)
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    if not hub.is_dir():
        return None
    matches = sorted(hub.glob(f"**/{_ANIME_FILE}"))
    if not matches:
        return None
    return str(matches[0])


def _anime_available() -> tuple[bool, str]:
    try:
        policy = weights_policy()
    except ValueError as exc:
        return False, str(exc)
    if policy == "offline" and _local_checkpoint() is None:
        return False, (
            "realesrgan-anime-6b weights are not cached and gif_upscale.weights_policy is offline."
        )
    return True, ""


def _refuse(reason: str):
    def upscale(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
        del frames, scale, opts
        raise AlgorithmError(reason)

    return upscale


def _upscale_anime(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
    del scale, opts
    ok, reason = _anime_available()
    if not ok:
        raise AlgorithmError(reason)
    from middleware.src.comfy_matrix import gpu_lease, try_admit
    from middleware.src.models.wrappers.esrgan_wrapper import ESRGANWrapper

    policy = weights_policy()
    local = _local_checkpoint()
    if policy == "offline" and local is None:
        raise AlgorithmError(
            "realesrgan-anime-6b weights are not cached and gif_upscale.weights_policy is offline."
        )
    refusal = try_admit("gif-upscale-realesrgan-anime-6b", estimated_gb=1.5, kind="generate")
    if refusal:
        raise AlgorithmError(refusal)
    try:
        # A local file is loaded directly. Offline mode never calls the Hub, even when
        # the only copy is the Hugging Face cache.
        wrapper = ESRGANWrapper(
            scale=4,
            num_block=6,
            checkpoint_path=local,
            local_files_only=policy == "offline",
        )
        output: list[np.ndarray] = []
        for frame in frames:
            rgb = np.clip(np.rint(frame[:, :, :3] * 255.0), 0, 255).astype(np.uint8)
            bgr = wrapper.upscale(rgb[:, :, ::-1])
            color = bgr[:, :, ::-1].astype(np.float32) / 255.0
            alpha = _nearest_alpha(frame[:, :, 3], color.shape[0], color.shape[1])
            output.append(np.dstack([color, alpha]))
        return output
    finally:
        gpu_lease.release("gif-upscale-realesrgan-anime-6b")


def _nearest_alpha(alpha: np.ndarray, height: int, width: int) -> np.ndarray:
    from PIL import Image

    image = Image.fromarray(np.clip(np.rint(alpha * 255.0), 0, 255).astype(np.uint8), "L")
    try:
        resized = image.resize((width, height), Image.Resampling.NEAREST)
        try:
            return np.asarray(resized).astype(np.float32) / 255.0
        finally:
            resized.close()
    finally:
        image.close()


register_algorithm(
    AlgorithmSpec(
        id="realesrgan-anime-6b",
        family="realesrgan",
        content="anime",
        kind="neural",
        supports_scale=frozenset({4.0}),
        supports_downscale=False,
        needs_gpu=True,
        vram_mb_estimate=1500,
        license="BSD-3-Clause",
        weights_sha256=None,
        available=_anime_available,
    ),
    _upscale_anime,
)

for _algorithm_id, _reason in _UNWIRED:
    register_algorithm(
        AlgorithmSpec(
            id=_algorithm_id,
            family="realesrgan",
            content="realistic" if "anime" not in _algorithm_id else "anime",
            kind="neural",
            supports_scale=frozenset({4.0} if _algorithm_id != "realesrgan-x2plus" else {2.0}),
            supports_downscale=False,
            needs_gpu=True,
            vram_mb_estimate=2000,
            license="BSD-3-Clause",
            weights_sha256=None,
            available=lambda reason=_reason: (False, reason),
        ),
        _refuse(_reason),
    )
