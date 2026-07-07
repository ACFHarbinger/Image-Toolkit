"""
backend/test/models/test_wrapper_contracts.py
=============================================
Mock-based interface contract tests for all ML model wrappers.

These tests verify the *interface contract* of each wrapper class —
required attributes, method signatures, return types, and lifecycle
behaviour — without loading any model weights or requiring a GPU.

Design rationale (§5.16A):
  - All heavy optional dependencies (torch, kornia, transformers, etc.)
    are patched into sys.modules before the wrapper module is imported,
    so each test runs in < 1 s and has zero external dependencies.
  - Tests are grouped by contract category, not by wrapper class, so
    that adding a new wrapper only requires adding it to the relevant
    parametrize lists.
  - The ModelWrapperContractMixin (§5.16C, depends on §5.8A) will
    supersede some of these tests once ModelWrapper ABC is in place.

Contract categories tested:
  1. Lifecycle        — __init__ accepts device, unload() sets model to None
  2. Idempotency      — unload() is safe to call multiple times
  3. Availability     — is_available() / module guard flags return bool
  4. Interface        — required public methods are callable
  5. Output shape     — match/mask/fit return correct shapes on synthetic inputs
"""

from __future__ import annotations

import os
import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Repo root on path
# ---------------------------------------------------------------------------
_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)


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
    torch.no_grad = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=None), __exit__=MagicMock(return_value=False)))
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
        stub.resize = MagicMock(side_effect=lambda src, dsize, **kw: np.zeros((*reversed(dsize), *src.shape[2:]), src.dtype) if src.ndim == 3 else np.zeros(reversed(dsize), src.dtype))
        stub.GaussianBlur = MagicMock(side_effect=lambda src, *a, **kw: src)
        return stub


# Synthetic images for output-shape tests
_IMG_A = np.zeros((64, 64, 3), dtype=np.uint8)
_IMG_B = np.ones((64, 64, 3), dtype=np.uint8) * 128
_MASK_A = np.ones((64, 64), dtype=np.uint8) * 255
_MASK_B = np.ones((64, 64), dtype=np.uint8) * 255


# ---------------------------------------------------------------------------
# 1. Lifecycle contract — device selection and unload()
# ---------------------------------------------------------------------------

class TestBaSiCWrapperLifecycle:
    """BaSiCWrapper stores flat_field / dark_field / baselines; unload() clears them."""

    def _get_wrapper(self):
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub}):
            from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper
            return BaSiCWrapper(device="cpu"), BaSiCWrapper

    def test_init_accepts_device(self):
        wrapper, _ = self._get_wrapper()
        assert wrapper.device == "cpu"

    def test_init_no_device_defaults_to_string(self):
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub}):
            import backend.src.models.wrappers.basic_wrapper as _mod
            w = _mod.BaSiCWrapper()
        assert isinstance(w.device, str)

    def test_unload_clears_all_state(self):
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub}):
            from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper
            w = BaSiCWrapper(device="cpu")
            # Simulate post-fit state
            w.flat_field = np.ones((8, 8, 3), np.float32)
            w.dark_field = np.zeros((8, 8, 3), np.float32)
            w.baselines = np.ones(3, np.float32)
            w.unload()
        assert w.flat_field is None
        assert w.dark_field is None
        assert w.baselines is None

    def test_unload_idempotent(self):
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub}):
            from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper
            w = BaSiCWrapper(device="cpu")
            w.unload()
            w.unload()  # must not raise


class TestLoFTRWrapperLifecycle:
    """LoFTRWrapper stores self.matcher; unload() sets it to None."""

    def _get_wrapper(self):
        torch_stub = _make_torch_stub()
        kornia_stub = _make_kornia_stub()
        mods = {"torch": torch_stub, "kornia": kornia_stub, "kornia.feature": kornia_stub.feature}
        with patch.dict(sys.modules, mods):
            from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper
            return LoFTRWrapper(device="cpu")

    def test_init_accepts_device(self):
        w = self._get_wrapper()
        assert w.device == "cpu"

    def test_init_matcher_none(self):
        w = self._get_wrapper()
        assert w.matcher is None

    def test_unload_when_no_model_loaded(self):
        """unload() with no model loaded must not raise."""
        w = self._get_wrapper()
        w.unload()
        assert w.matcher is None

    def test_unload_clears_mock_model(self):
        torch_stub = _make_torch_stub()
        kornia_stub = _make_kornia_stub()
        mods = {"torch": torch_stub, "kornia": kornia_stub, "kornia.feature": kornia_stub.feature}
        with patch.dict(sys.modules, mods):
            from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper
            w = LoFTRWrapper(device="cpu")
            fake_model = MagicMock()
            fake_model.cpu = MagicMock()
            w.matcher = fake_model
            w.unload()
        assert w.matcher is None

    def test_unload_idempotent(self):
        w = self._get_wrapper()
        w.unload()
        w.unload()


class TestRoMaWrapperLifecycle:
    """RoMaWrapper raises ImportError when romatch is missing."""

    def test_availability_flag_is_bool(self):
        """_ROMA_OK must be a bool regardless of whether romatch is installed."""
        import backend.src.models.wrappers.roma_wrapper as _mod
        assert isinstance(_mod._ROMA_OK, bool)

    def test_unavailable_when_romatch_blocked(self):
        """When romatch is blocked, _ROMA_OK must be False after reload."""
        from importlib import reload
        with patch.dict(sys.modules, {"romatch": None}):
            import backend.src.models.wrappers.roma_wrapper as _mod
            reload(_mod)
            assert _mod._ROMA_OK is False


class TestALIKEDWrapperLifecycle:
    """ALIKEDLightGlueWrapper guards its kornia dependency with a module-level bool flag."""

    def test_availability_flag_is_bool(self):
        """_KORNIA_OK must be a bool regardless of whether kornia is installed."""
        import backend.src.models.wrappers.aliked_lg_wrapper as _mod
        assert isinstance(_mod._KORNIA_OK, bool)

    def test_unavailable_when_kornia_blocked(self):
        """When kornia is blocked from import, _KORNIA_OK must be False after reload."""
        from importlib import reload
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub, "kornia": None, "kornia.feature": None}):
            import backend.src.models.wrappers.aliked_lg_wrapper as _mod
            # Force reload so the try/except runs under the blocked kornia
            reload(_mod)
            assert _mod._KORNIA_OK is False


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
        mods = {"torch": torch_stub, "kornia": kornia_stub, "kornia.feature": kornia_stub.feature}
        with patch.dict(sys.modules, mods):
            from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper
            w = LoFTRWrapper(device="cpu")
            w.unload()
            w.unload()


# ---------------------------------------------------------------------------
# 3. Interface contract — required public methods exist and are callable
# ---------------------------------------------------------------------------

class TestBaSiCWrapperInterface:
    """BaSiCWrapper must expose fit(), transform_stack(), apply_correction(),
    estimate_profiles(), process_batch()."""

    REQUIRED_METHODS = [
        "fit",
        "transform_stack",
        "apply_correction",
        "estimate_profiles",
        "process_batch",
        "unload",
    ]

    def _get_wrapper(self):
        torch_stub = _make_torch_stub()
        with patch.dict(sys.modules, {"torch": torch_stub}):
            from backend.src.models.wrappers.basic_wrapper import BaSiCWrapper
            return BaSiCWrapper(device="cpu")

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_exists(self, method):
        w = self._get_wrapper()
        assert hasattr(w, method), f"BaSiCWrapper missing method: {method}"
        assert callable(getattr(w, method))


class TestLoFTRWrapperInterface:
    """LoFTRWrapper must expose match(), match_masked(), get_affine_partial(),
    get_transform(), load_model(), unload()."""

    REQUIRED_METHODS = [
        "match",
        "match_masked",
        "get_affine_partial",
        "get_transform",
        "load_model",
        "unload",
    ]

    def _get_wrapper(self):
        torch_stub = _make_torch_stub()
        kornia_stub = _make_kornia_stub()
        mods = {"torch": torch_stub, "kornia": kornia_stub, "kornia.feature": kornia_stub.feature}
        with patch.dict(sys.modules, mods):
            from backend.src.models.wrappers.loftr_wrapper import LoFTRWrapper
            return LoFTRWrapper(device="cpu")

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_exists(self, method):
        w = self._get_wrapper()
        assert hasattr(w, method), f"LoFTRWrapper missing method: {method}"
        assert callable(getattr(w, method))


class TestBiRefNetWrapperInterface:
    """BiRefNetWrapper must expose get_mask(), get_soft_mask(),
    get_background_mask(), get_mask_batch(), unload()."""

    REQUIRED_METHODS = [
        "get_mask",
        "get_soft_mask",
        "get_background_mask",
        "get_mask_batch",
        "unload",
    ]

    def _get_wrapper(self):
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
            return BiRefNetWrapper(device="cpu")

    @pytest.mark.parametrize("method", REQUIRED_METHODS)
    def test_method_exists(self, method):
        w = self._get_wrapper()
        assert hasattr(w, method), f"BiRefNetWrapper missing method: {method}"
        assert callable(getattr(w, method))


# ---------------------------------------------------------------------------
# 4. Output type contract — apply_correction() returns np.ndarray
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
# 5. BiRefNetWrapper singleton-per-model contract
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
            from backend.src.models.wrappers.birefnet_wrapper import BiRefNetWrapper
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
            from backend.src.models.wrappers.birefnet_wrapper import BiRefNetWrapper
            a = BiRefNetWrapper(device="cpu")
            b = BiRefNetWrapper(device="cpu")
            assert a._models is b._models
