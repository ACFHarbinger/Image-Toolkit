"""
backend/test/models/test_wrapper_contracts.py
=============================================
Mock-based interface contract tests for all ML model wrappers.

These tests verify the *interface contract* of each wrapper class —
required attributes, method signatures, return types, and lifecycle
behaviour — without loading any model weights or requiring a GPU.

Design rationale (§5.16A / §5.16C, #625):
  - All heavy optional dependencies (torch, kornia, transformers, etc.)
    are patched into sys.modules before the wrapper module is imported,
    so each test runs in < 1 s and has zero external dependencies.
  - The shared contract assertions (availability, lifecycle, device selection,
    unload idempotency, ModelRegistry integration) are factored into
    ModelWrapperContractMixin (§5.16C).
  - Wrapper-specific interface methods and domain tests are composed onto
    each wrapper contract class.
"""

from __future__ import annotations

import os
import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np

# ---------------------------------------------------------------------------
# Repo root on path & submodule bootstrap
# ---------------------------------------------------------------------------
_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

from git.scripts._submodule_bootstrap import (  # noqa: E402
    register_submodule_packages,
)

register_submodule_packages(_repo_root)

from backend.test.models._contract_mixin import (  # noqa: E402
    ModelWrapperContractMixin,
)

# ---------------------------------------------------------------------------
# Helpers: lightweight torch / kornia / transformers stubs
# ---------------------------------------------------------------------------

def _make_torch_stub() -> types.ModuleType:
    """Minimal torch stub sufficient for wrapper __init__ and unload()."""
    torch = types.ModuleType("torch")
    torch.cuda = MagicMock()
    torch.cuda.is_available = MagicMock(return_value=False)
    torch.cuda.empty_cache = MagicMock()
    torch.device = MagicMock(side_effect=lambda x: x)
    torch.no_grad = MagicMock(
        return_value=MagicMock(
            __enter__=MagicMock(return_value=None),
            __exit__=MagicMock(return_value=False),
        )
    )
    torch.backends = MagicMock()
    torch.backends.cudnn = MagicMock()
    torch.backends.cudnn.benchmark = False
    # tensor ops used by BaSiCWrapper.fit
    torch.from_numpy = MagicMock(return_value=MagicMock())
    torch.stack = MagicMock(return_value=MagicMock())
    torch.median = MagicMock(return_value=(MagicMock(), MagicMock()))
    torch.Tensor = MagicMock
    return torch


def _make_kornia_stub() -> types.ModuleType:
    kornia = types.ModuleType("kornia")
    kornia.feature = MagicMock()
    return kornia


def _make_transformers_stub() -> types.ModuleType:
    t = types.ModuleType("transformers")
    t.AutoModelForImageSegmentation = MagicMock()
    t.AutoImageProcessor = MagicMock()
    t.EfficientLoFTRForKeypointMatching = MagicMock()
    t.configuration_utils = types.ModuleType("transformers.configuration_utils")
    t.configuration_utils.PretrainedConfig = MagicMock()
    return t


def _make_cv2_stub():
    """cv2 is usually available; return real cv2 or a stub."""
    try:
        import cv2

        return cv2
    except ImportError:
        stub = types.ModuleType("cv2")
        stub.INTER_AREA = 3
        stub.INTER_LINEAR = 1
        stub.imread = MagicMock(return_value=np.zeros((64, 64, 3), np.uint8))
        stub.cvtColor = MagicMock(return_value=np.zeros((64, 64), np.uint8))
        stub.resize = MagicMock(
            side_effect=lambda src, dsize, **kw: (
                np.zeros((*reversed(dsize), *src.shape[2:]), src.dtype)
                if src.ndim == 3
                else np.zeros(reversed(dsize), src.dtype)
            )
        )
        stub.GaussianBlur = MagicMock(side_effect=lambda src, *a, **kw: src)
        return stub


# Synthetic images for output-shape tests
_IMG_A = np.zeros((64, 64, 3), dtype=np.uint8)
_IMG_B = np.ones((64, 64, 3), dtype=np.uint8) * 128
_MASK_A = np.ones((64, 64), dtype=np.uint8) * 255
_MASK_B = np.ones((64, 64), dtype=np.uint8) * 255


# ---------------------------------------------------------------------------
# 1. Wrapper contract test classes (using ModelWrapperContractMixin, §5.16C)
# ---------------------------------------------------------------------------

class TestBaSiCWrapperContract(ModelWrapperContractMixin):
    """Contract tests for BaSiCWrapper (flat-field illumination estimation)."""

    from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper

    wrapper_class = BaSiCWrapper
    required_methods = [
        "fit",
        "transform_stack",
        "apply_correction",
        "estimate_profiles",
        "process_batch",
        "unload",
    ]

    def get_wrapper(self, device: str | None = "cpu"):
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub}):
            from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper

            return BaSiCWrapper(device=device)

    def simulate_loaded(self, wrapper):
        wrapper.flat_field = np.ones((8, 8, 3), np.float32)

    def test_unload_clears_all_state(self):
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub}):
            from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper

            w = BaSiCWrapper(device="cpu")
            w.flat_field = np.ones((8, 8, 3), np.float32)
            w.dark_field = np.zeros((8, 8, 3), np.float32)
            w.baselines = np.ones(3, np.float32)
            w.unload()
        assert w.flat_field is None
        assert w.dark_field is None
        assert w.baselines is None
        assert not w.loaded


class TestLoFTRWrapperContract(ModelWrapperContractMixin):
    """Contract tests for LoFTRWrapper (dense feature matcher)."""

    from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper

    wrapper_class = LoFTRWrapper
    required_methods = [
        "match",
        "match_masked",
        "get_affine_partial",
        "get_transform",
        "load_model",
        "unload",
    ]

    def get_wrapper(self, device: str | None = "cpu"):
        torch_stub = _make_torch_stub()
        kornia_stub = _make_kornia_stub()
        mods = {
            "torch": torch_stub,
            "kornia": kornia_stub,
            "kornia.feature": kornia_stub.feature,
        }
        with patch.dict(sys.modules, mods):
            from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper

            return LoFTRWrapper(device=device)

    def simulate_loaded(self, wrapper):
        fake_model = MagicMock()
        fake_model.cpu = MagicMock()
        wrapper.matcher = fake_model

    def test_init_matcher_none(self):
        w = self.get_wrapper()
        assert w.matcher is None


class TestBiRefNetWrapperContract(ModelWrapperContractMixin):
    """Contract tests for BiRefNetWrapper (background segmentation)."""

    from backend.src.models.wrappers.birefnet_wrapper import BiRefNetWrapper

    wrapper_class = BiRefNetWrapper
    required_methods = [
        "get_mask",
        "get_soft_mask",
        "get_background_mask",
        "get_mask_batch",
        "unload",
    ]

    def get_wrapper(self, device: str | None = "cpu"):
        torch_stub = _make_torch_stub()
        transformers_stub = _make_transformers_stub()
        torchvision_stub = types.ModuleType("torchvision")
        torchvision_stub.transforms = MagicMock()
        pil_stub = types.ModuleType("PIL")
        pil_stub.Image = MagicMock()
        mods = {
            "torch": torch_stub,
            "transformers": transformers_stub,
            "transformers.configuration_utils": transformers_stub.configuration_utils,
            "torchvision": torchvision_stub,
            "PIL": pil_stub,
            "PIL.Image": pil_stub.Image,
        }
        with patch.dict(sys.modules, mods):
            from backend.src.models.wrappers.birefnet_wrapper import BiRefNetWrapper

            return BiRefNetWrapper(device=device)

    def simulate_loaded(self, wrapper):
        fake = MagicMock()
        fake.cpu = MagicMock()
        self.wrapper_class._models[(wrapper.model_name, wrapper.device)] = fake


class TestRoMaWrapperContract(ModelWrapperContractMixin):
    """Contract tests for RoMaWrapper (dense warp matcher)."""

    import asp_backend.models.wrappers.roma_wrapper as _roma_mod

    wrapper_class = _roma_mod.RoMaWrapper
    required_methods = [
        "match_translation",
        "load",
        "unload",
        "offload",
        "is_available",
    ]

    def get_wrapper(self, device: str | None = "cpu"):
        torch_stub = _make_torch_stub()
        romatch_stub = types.ModuleType("romatch")
        romatch_stub.roma_outdoor = MagicMock()
        mods = {"torch": torch_stub, "romatch": romatch_stub}
        with patch.dict(sys.modules, mods):
            import asp_backend.models.wrappers.roma_wrapper as _mod

            with patch.object(_mod, "_ROMA_OK", True):
                return _mod.RoMaWrapper(device=device)

    def test_availability_flag_is_bool(self):
        """_ROMA_OK must be a bool regardless of whether romatch is installed."""
        import asp_backend.models.wrappers.roma_wrapper as _mod

        assert isinstance(_mod._ROMA_OK, bool)

    def test_unavailable_when_romatch_blocked(self):
        """When romatch is blocked, _ROMA_OK must be False after reload."""
        from importlib import reload

        with patch.dict(sys.modules, {"romatch": None}):
            import asp_backend.models.wrappers.roma_wrapper as _mod

            reload(_mod)
            assert _mod._ROMA_OK is False


class TestALIKEDWrapperContract(ModelWrapperContractMixin):
    """Contract tests for ALIKEDLightGlueWrapper (keypoint detector + matcher)."""

    import asp_backend.models.wrappers.aliked_lg_wrapper as _aliked_mod

    wrapper_class = _aliked_mod.ALIKEDLightGlueWrapper
    required_methods = [
        "match",
        "get_translation",
        "load",
        "unload",
        "offload",
        "is_available",
    ]

    def get_wrapper(self, device: str | None = "cpu"):
        torch_stub = _make_torch_stub()
        kornia_stub = _make_kornia_stub()
        mods = {
            "torch": torch_stub,
            "kornia": kornia_stub,
            "kornia.feature": kornia_stub.feature,
        }
        with patch.dict(sys.modules, mods):
            import asp_backend.models.wrappers.aliked_lg_wrapper as _mod

            with patch.object(_mod, "_KORNIA_OK", True):
                return _mod.ALIKEDLightGlueWrapper(device=device)

    def simulate_loaded(self, wrapper):
        fake = MagicMock()
        fake.cpu = MagicMock()
        wrapper._detector = fake
        wrapper._lightglue = fake

    def test_availability_flag_is_bool(self):
        """_KORNIA_OK must be a bool regardless of whether kornia is installed."""
        import asp_backend.models.wrappers.aliked_lg_wrapper as _mod

        assert isinstance(_mod._KORNIA_OK, bool)

    def test_unavailable_when_kornia_blocked(self):
        """When kornia is blocked from import, _KORNIA_OK must be False after reload."""
        from importlib import reload

        torch_stub = _make_torch_stub()
        with patch.dict(
            sys.modules,
            {"torch": torch_stub, "kornia": None, "kornia.feature": None},
        ):
            import asp_backend.models.wrappers.aliked_lg_wrapper as _mod

            reload(_mod)
            assert _mod._KORNIA_OK is False


class TestEfficientLoFTRWrapperContract(ModelWrapperContractMixin):
    """Contract tests for EfficientLoFTRWrapper (HuggingFace EfficientLoFTR)."""

    import asp_backend.models.wrappers.efficient_loftr_wrapper as _eloftr_mod

    wrapper_class = _eloftr_mod.EfficientLoFTRWrapper
    required_methods = [
        "match",
        "match_masked",
        "get_affine_partial",
        "get_transform",
        "load",
        "unload",
        "offload",
        "is_available",
    ]

    def get_wrapper(self, device: str | None = "cpu"):
        torch_stub = _make_torch_stub()
        transformers_stub = _make_transformers_stub()
        mods = {
            "torch": torch_stub,
            "transformers": transformers_stub,
            "transformers.configuration_utils": transformers_stub.configuration_utils,
        }
        with patch.dict(sys.modules, mods):
            import asp_backend.models.wrappers.efficient_loftr_wrapper as _mod

            with patch.object(_mod, "_TRANSFORMERS_OK", True):
                return _mod.EfficientLoFTRWrapper(device=device)

    def test_availability_flag_is_bool(self):
        """_TRANSFORMERS_OK must be a bool regardless of whether transformers is installed."""
        import asp_backend.models.wrappers.efficient_loftr_wrapper as _mod

        assert isinstance(_mod._TRANSFORMERS_OK, bool)

    def test_unavailable_when_transformers_blocked(self):
        """When transformers is blocked, _TRANSFORMERS_OK must be False after reload."""
        from importlib import reload

        with patch.dict(sys.modules, {"transformers": None}):
            import asp_backend.models.wrappers.efficient_loftr_wrapper as _mod

            reload(_mod)
            assert _mod._TRANSFORMERS_OK is False


class TestJamMaWrapperContract(ModelWrapperContractMixin):
    """Contract tests for JamMaWrapper (Mamba-based feature matcher)."""

    import asp_backend.models.wrappers.jamma_wrapper as _jamma_mod

    wrapper_class = _jamma_mod.JamMaWrapper
    required_methods = [
        "match",
        "match_masked",
        "get_affine_partial",
        "load",
        "unload",
        "offload",
        "is_available",
    ]

    def get_wrapper(self, device: str | None = "cpu"):
        torch_stub = _make_torch_stub()
        mamba_stub = types.ModuleType("mamba_ssm")
        mods = {"torch": torch_stub, "mamba_ssm": mamba_stub}
        with patch.dict(sys.modules, mods):
            import asp_backend.models.wrappers.jamma_wrapper as _mod

            with patch.object(_mod, "_JAMMA_OK", True):
                return _mod.JamMaWrapper(device=device)

    def test_availability_flag_is_bool(self):
        """_JAMMA_OK must be a bool regardless of whether mamba_ssm is installed."""
        import asp_backend.models.wrappers.jamma_wrapper as _mod

        assert isinstance(_mod._JAMMA_OK, bool)

    def test_unavailable_when_mamba_blocked(self):
        """When mamba_ssm is blocked, _JAMMA_OK must be False after reload."""
        from importlib import reload

        with patch.dict(sys.modules, {"mamba_ssm": None}):
            import asp_backend.models.wrappers.jamma_wrapper as _mod

            reload(_mod)
            assert _mod._JAMMA_OK is False


class TestESRGANWrapperContract(ModelWrapperContractMixin):
    """Contract tests for ESRGANWrapper (anime tiled super-resolution)."""

    from backend.src.models.wrappers.esrgan_wrapper import ESRGANWrapper

    wrapper_class = ESRGANWrapper
    required_methods = [
        "upscale",
        "upscale_path",
        "load",
        "unload",
        "is_available",
    ]

    def get_wrapper(self, device: str | None = "cpu"):
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub}):
            from backend.src.models.wrappers.esrgan_wrapper import ESRGANWrapper

            return ESRGANWrapper(device=device)


class TestWDTaggerWrapperContract(ModelWrapperContractMixin):
    """Contract tests for WDTaggerWrapper (WD-1.4 ONNX tagger)."""

    from backend.src.models.wrappers.wd_tagger_wrapper import WDTaggerWrapper

    wrapper_class = WDTaggerWrapper
    required_methods = [
        "tag",
        "tag_batch",
        "tag_with_review",
        "load",
        "unload",
        "is_available",
    ]

    def get_wrapper(self, device: str | None = "cpu"):
        from backend.src.models.wrappers.wd_tagger_wrapper import WDTaggerWrapper

        return WDTaggerWrapper(device=device)

    def simulate_loaded(self, wrapper):
        wrapper._session = MagicMock()


# ---------------------------------------------------------------------------
# 2. Idempotency contract — double-unload must never raise
# ---------------------------------------------------------------------------

class TestUnloadIdempotency:
    """
    For every wrapper that can be instantiated without loading model weights,
    unload() must be safely callable twice (once after init with no model,
    once after first unload).
    """

    def test_basic_wrapper_double_unload(self):
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub}):
            from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper

            w = BaSiCWrapper(device="cpu")
            w.unload()
            w.unload()

    def test_loftr_wrapper_double_unload(self):
        torch_stub = _make_torch_stub()
        kornia_stub = _make_kornia_stub()
        mods = {
            "torch": torch_stub,
            "kornia": kornia_stub,
            "kornia.feature": kornia_stub.feature,
        }
        with patch.dict(sys.modules, mods):
            from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper

            w = LoFTRWrapper(device="cpu")
            w.unload()
            w.unload()


# ---------------------------------------------------------------------------
# 3. Output type contract — apply_correction() returns np.ndarray
# ---------------------------------------------------------------------------

class TestBaSiCOutputTypes:
    """apply_correction() must return np.ndarray of the same shape as input."""

    def test_apply_correction_returns_ndarray(self):
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub}):
            from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper

            w = BaSiCWrapper(device="cpu")
            img = np.zeros((64, 64, 3), dtype=np.uint8)
            # Before fit, flat_field is None — apply_correction returns the original
            result = w.apply_correction(img)
        assert isinstance(result, np.ndarray)
        assert result.shape == img.shape

    def test_apply_correction_no_fit_returns_input(self):
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub}):
            from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper

            w = BaSiCWrapper(device="cpu")
            img = np.zeros((32, 32, 3), dtype=np.uint8) + 200
            result = w.apply_correction(img)
        # flat_field is None → returns input unchanged
        np.testing.assert_array_equal(result, img)


# ---------------------------------------------------------------------------
# 4. BiRefNetWrapper singleton-per-model contract
# ---------------------------------------------------------------------------

class TestBiRefNetSingleton:
    """BiRefNetWrapper._models is a class-level dict shared across instances."""

    def test_models_dict_is_class_attribute(self):
        torch_stub = _make_torch_stub()
        transformers_stub = _make_transformers_stub()
        torchvision_stub = types.ModuleType("torchvision")
        torchvision_stub.transforms = MagicMock()
        pil_stub = types.ModuleType("PIL")
        pil_stub.Image = MagicMock()
        mods = {
            "torch": torch_stub,
            "transformers": transformers_stub,
            "transformers.configuration_utils": transformers_stub.configuration_utils,
            "torchvision": torchvision_stub,
            "PIL": pil_stub,
            "PIL.Image": pil_stub.Image,
        }
        with patch.dict(sys.modules, mods):
            from backend.src.models.wrappers.birefnet_wrapper import (
                BiRefNetWrapper,
            )

            assert hasattr(BiRefNetWrapper, "_models")
            assert isinstance(BiRefNetWrapper._models, dict)

    def test_two_instances_share_models_dict(self):
        torch_stub = _make_torch_stub()
        transformers_stub = _make_transformers_stub()
        torchvision_stub = types.ModuleType("torchvision")
        torchvision_stub.transforms = MagicMock()
        pil_stub = types.ModuleType("PIL")
        pil_stub.Image = MagicMock()
        mods = {
            "torch": torch_stub,
            "transformers": transformers_stub,
            "transformers.configuration_utils": transformers_stub.configuration_utils,
            "torchvision": torchvision_stub,
            "PIL": pil_stub,
            "PIL.Image": pil_stub.Image,
        }
        with patch.dict(sys.modules, mods):
            from backend.src.models.wrappers.birefnet_wrapper import (
                BiRefNetWrapper,
            )

            a = BiRefNetWrapper(device="cpu")
            b = BiRefNetWrapper(device="cpu")
            assert a._models is b._models


# ---------------------------------------------------------------------------
# 5. ModelWrapper allocation & CUDA flush policy contract
# ---------------------------------------------------------------------------

class TestModelWrapperCudaFlushPolicy:
    """Allocator synchronization is diagnostic-only during unload."""

    @staticmethod
    def _wrapper_class():
        from backend.src.models.core.base import ModelWrapper

        class _Wrapper(ModelWrapper):
            def load(self) -> None:
                pass

        return _Wrapper

    def test_unload_does_not_flush_cuda_by_default(self, monkeypatch):
        torch_stub = _make_torch_stub()
        torch_stub.cuda.is_available.return_value = True
        monkeypatch.delenv("ITK_MODEL_FLUSH_CUDA_ON_UNLOAD", raising=False)
        with patch.dict(sys.modules, {"torch": torch_stub}):
            self._wrapper_class()(device="cuda").unload()
        torch_stub.cuda.empty_cache.assert_not_called()

    def test_unload_flush_can_be_enabled_for_diagnostics(self, monkeypatch):
        torch_stub = _make_torch_stub()
        torch_stub.cuda.is_available.return_value = True
        monkeypatch.setenv("ITK_MODEL_FLUSH_CUDA_ON_UNLOAD", "1")
        with patch.dict(sys.modules, {"torch": torch_stub}):
            self._wrapper_class()(device="cuda").unload()
        torch_stub.cuda.empty_cache.assert_called_once_with()
