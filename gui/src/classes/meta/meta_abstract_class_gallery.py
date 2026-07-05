from abc import ABCMeta

from PySide6.QtCore import QObject


class MetaAbstractClassGallery(ABCMeta, type(QObject)):
    """Fuses ABCMeta with Qt's Shiboken metaclass.

    PySide6 uses ``Shiboken.ObjectType`` as the metaclass for all ``QObject``
    subclasses.  Combining that with ``ABCMeta`` (needed for ``@abstractmethod``
    enforcement) requires an explicit merge — Python raises ``TypeError`` when a
    class has two incompatible metaclasses.  This class resolves the conflict.

    All shared helper methods (``common_*``) previously injected by this metaclass
    now live as normal inherited methods on ``AbstractGalleryBase``
    (``gui.src.classes.gallery_base``).  The metaclass no longer injects anything;
    it exists solely as the combined metaclass required for the QWidget + ABCMeta
    inheritance.
    """
