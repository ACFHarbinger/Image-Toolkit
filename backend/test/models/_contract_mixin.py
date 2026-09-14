"""
backend/test/models/_contract_mixin.py
======================================
Shared contract test mixin for all ModelWrapper subclasses (§5.16 Option C, #625).
"""

from __future__ import annotations

from typing import ClassVar, Sequence, Type
from unittest.mock import MagicMock

from backend.src.models.core.base import ModelRegistry, ModelWrapper


class ModelWrapperContractMixin:
    """Reusable contract test mixin for all ModelWrapper subclasses.

    Verifies the fundamental contract required by ModelWrapper (§5.8A / §5.16C):
    1. Base class: class must inherit from ModelWrapper.
    2. Availability: is_available() class method exists and returns a bool.
    3. Lifecycle initial state: unloaded when instantiated (loaded == False).
    4. Lifecycle __new__: raw instance before initialization has loaded == False.
    5. Device selection: accepts device parameter, defaults to string ("cpu" or "cuda").
    6. Unload safety: unload() succeeds when not loaded, and is idempotent.
    7. Unload state cleanup: unload() clears simulated loaded state (loaded becomes False).
    8. Load method: load() method is defined and callable.
    9. Interface / public methods: required_methods exist and are callable.
    10. Registry integration: initializing the wrapper registers it in ModelRegistry.
    """

    wrapper_class: ClassVar[Type[ModelWrapper]]
    required_methods: ClassVar[Sequence[str]] = ()

    def get_wrapper(self, device: str | None = "cpu") -> ModelWrapper:
        """Create a wrapper instance with mocked/stubbed dependencies as needed.

        Subclasses should override this if the wrapper requires patched
        dependencies or custom constructor arguments.
        """
        return self.wrapper_class(device=device)

    def simulate_loaded(self, wrapper: ModelWrapper) -> None:
        """Attach fake model state so loaded becomes True.

        Subclasses whose loaded property checks a different attribute (e.g.
        ``self.matcher`` or ``self.flat_field``) should override this.
        """
        wrapper._model = MagicMock()

    def test_is_subclass_of_model_wrapper(self) -> None:
        """Wrapper class must inherit from ModelWrapper ABC."""
        assert issubclass(self.wrapper_class, ModelWrapper), (
            f"{self.wrapper_class.__name__} must inherit from ModelWrapper"
        )

    def test_is_available_returns_bool(self) -> None:
        """is_available() class method must return a bool."""
        available = self.wrapper_class.is_available()
        assert isinstance(available, bool), (
            f"{self.wrapper_class.__name__}.is_available() returned {type(available)}, expected bool"
        )

    def test_loaded_initially_false_raw_instance(self) -> None:
        """An uninitialized raw instance (__new__) must not report loaded == True."""
        w = self.wrapper_class.__new__(self.wrapper_class)
        try:
            loaded = w.loaded
        except AttributeError:
            loaded = False
        assert not loaded, f"{self.wrapper_class.__name__}.loaded must be False before load() / initialization"

    def test_loaded_initially_false(self) -> None:
        """Newly instantiated wrapper must not have model resident in memory."""
        w = self.get_wrapper(device="cpu")
        assert not w.loaded, f"{self.wrapper_class.__name__}.loaded should be False initially"

    def test_init_accepts_device(self) -> None:
        """__init__ must store device string properly."""
        w = self.get_wrapper(device="cpu")
        assert w.device == "cpu"
        assert isinstance(w.device, str)

    def test_init_no_device_defaults_to_string(self) -> None:
        """__init__ with device=None must default to a device string ('cpu' or 'cuda')."""
        w = self.get_wrapper(device=None)
        assert isinstance(w.device, str)
        assert len(w.device) > 0

    def test_unload_when_no_model_loaded(self) -> None:
        """unload() with no model loaded must not raise."""
        w = self.get_wrapper(device="cpu")
        w.unload()
        assert not w.loaded

    def test_unload_is_idempotent(self) -> None:
        """unload() must be safe to call multiple times without error and leave loaded == False."""
        w = self.get_wrapper(device="cpu")
        w.unload()
        w.unload()
        assert not w.loaded

    def test_unload_clears_mock_model(self) -> None:
        """unload() after model is resident must set loaded to False."""
        w = self.get_wrapper(device="cpu")
        self.simulate_loaded(w)
        if w.loaded:
            w.unload()
            assert not w.loaded

    def test_load_method_exists(self) -> None:
        """Wrapper must define a callable load() method."""
        w = self.get_wrapper(device="cpu")
        assert hasattr(w, "load"), f"{self.wrapper_class.__name__} missing load() method"
        assert callable(w.load), f"{self.wrapper_class.__name__}.load is not callable"

    def test_required_methods_exist(self) -> None:
        """All required public interface methods must exist and be callable."""
        w = self.get_wrapper(device="cpu")
        for method_name in self.required_methods:
            assert hasattr(w, method_name), f"{self.wrapper_class.__name__} missing required method: {method_name}"
            assert callable(getattr(w, method_name)), f"{self.wrapper_class.__name__}.{method_name} is not callable"

    def test_model_registry_registration(self) -> None:
        """Instantiating the wrapper must register it in ModelRegistry."""
        w = self.get_wrapper(device="cpu")
        live = [ref() for ref in ModelRegistry._refs if ref() is not None]
        assert w in live, f"{self.wrapper_class.__name__} instance was not registered in ModelRegistry"


__all__ = ["ModelWrapperContractMixin"]
