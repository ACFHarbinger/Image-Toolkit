"""Metadata Editor Window — launched when the user clicks Add/Update N Selected Images.

Layout
------
  Tab 0 : "Batch / Overview"  — set metadata for all images at once, or define
           named *clusters* (subsets of images) each with their own config.
           A pattern-mode fills sequential fields (name1, name2 …) automatically.
  Tab 1…N : one tab per selected image, showing a small thumbnail + individual
             editable fields whose values start pre-filled from the Batch tab.

On "Confirm and Save" the caller receives a list of per-image dicts via the
``metadata_confirmed`` signal so ``ScanMetadataTab`` can do the actual DB
writes without importing Qt.
"""

from ._filtered_tag_list import FilteredTagList
from .manager import MetadataEditorWindow

__all__ = ["MetadataEditorWindow", "FilteredTagList"]
