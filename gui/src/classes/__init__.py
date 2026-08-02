"""
gui.src.classes
===============
Base classes and metaclasses for PySide6 gallery tabs (§5.10 & §5.12 Architecture).

Class Hierarchy
---------------
```mermaid
classDiagram
    class QWidget
    class MetaAbstractClassGallery
    class AbstractGalleryBase {
        <<abstract>>
        +thumbnail_size: int
        +found_page_size: int
        +common_filter_string_list()
        +common_load_page()
    }
    class AbstractClassSingleGallery {
        <<abstract>>
        +load_directory()
    }
    class AbstractClassTwoGalleries {
        <<abstract>>
        +found_files: list
        +selected_files: list
        +handle_marquee_selection()
    }

    QWidget <|-- AbstractGalleryBase
    AbstractGalleryBase <|-- AbstractClassSingleGallery
    AbstractGalleryBase <|-- AbstractClassTwoGalleries
    MetaAbstractClassGallery ..> AbstractClassSingleGallery : metaclass
    MetaAbstractClassGallery ..> AbstractClassTwoGalleries : metaclass
```
"""
from .image.abstract_class_single_gallery import (
    AbstractClassSingleGallery as AbstractClassSingleGallery,
)
from .image.abstract_class_two_galleries import (
    AbstractClassTwoGalleries as AbstractClassTwoGalleries,
)
from .base import (
    AbstractGalleryBase as AbstractGalleryBase,
)
from .base import (
    BaseGenerativeTab as BaseGenerativeTab,
)
from .meta import (
    MetaAbstractClassGallery as MetaAbstractClassGallery,
)

__all__ = [
    "AbstractClassSingleGallery",
    "AbstractClassTwoGalleries",
    "AbstractGalleryBase",
    "BaseGenerativeTab",
    "MetaAbstractClassGallery",
]

