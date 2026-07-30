"""
backend.src.models
==================
PyTorch and ONNX model wrappers for feature extraction, matching, background removal,
and anime image processing (§5.12 & §5.8 Architecture).

Class Hierarchy
---------------
```mermaid
classDiagram
    class ModelWrapper {
        <<abstract>>
        +str device
        +load()*
        +unload()
        +is_available() bool
        +bool loaded
    }
    class ModelRegistry {
        +register(wrapper)
        +unload_all()
        +loaded_count() int
        +clear()
    }
    class BiRefNetWrapper {
        +get_mask(img)
    }
    class LoFTRWrapper {
        +match(img1, img2)
    }
    class EfficientLoFTRWrapper {
        +match(img1, img2)
    }
    class RoMaWrapper {
        +match(img1, img2)
    }
    class ALIKEDLGWrapper {
        +match(img1, img2)
    }
    class JamMaWrapper {
        +match(img1, img2)
    }
    class BaSiCWrapper {
        +restore(img)
    }
    class WDTaggerWrapper {
        +tag(img)
        +tag_with_review(img)
    }

    ModelWrapper <|-- BiRefNetWrapper
    ModelWrapper <|-- LoFTRWrapper
    ModelWrapper <|-- EfficientLoFTRWrapper
    ModelWrapper <|-- RoMaWrapper
    ModelWrapper <|-- ALIKEDLGWrapper
    ModelWrapper <|-- JamMaWrapper
    ModelWrapper <|-- BaSiCWrapper
    ModelWrapper <|-- WDTaggerWrapper
    ModelRegistry o-- ModelWrapper
```

Note (§3.14): wrapper classes are NOT eagerly imported here.
All callers use the full module path (e.g. from backend.src.models.wrappers.birefnet_wrapper import ...)
so there is no need to re-export them from this package __init__.
"""
from .core.base import ModelRegistry, ModelWrapper, lazy_load

__all__ = [
    "ModelWrapper",
    "ModelRegistry",
    "lazy_load",
]

