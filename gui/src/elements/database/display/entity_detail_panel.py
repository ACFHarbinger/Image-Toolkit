"""Entity detail panel (listings database).

Split (§5.17 Option B, #629) into :mod:`_entity_panel_form` (form shell:
layout build, load/clear, collect/save/delete) and
:mod:`_entity_panel_relations` (tags, credits, linked images,
associations) — pure code motion, no logic change. This module keeps the
public surface.
"""

from __future__ import annotations

from PySide6.QtCore import Signal

from ._entity_panel_form import _EntityPanelFormMixin
from ._entity_panel_relations import _EntityPanelRelationsMixin


class _EntityDetailPanel(_EntityPanelFormMixin, _EntityPanelRelationsMixin):
    saved = Signal(dict)
    deleted = Signal(str)


__all__ = ["_EntityDetailPanel"]
