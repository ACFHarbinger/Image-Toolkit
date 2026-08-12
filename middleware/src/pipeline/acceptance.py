"""Explicit, auditable acceptance of frontend assistance proposals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..document import Document, DocumentHistory
from .orchestrator import PipelineProposal


@dataclass(frozen=True)
class AcceptedProposal:
    """Audit record for a proposal accepted by the user."""

    kind: str
    name: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "name": self.name, "proposal": self.payload}


class ProposalAcceptanceService:
    """Commit accepted proposals without silently performing pixel edits.

    Operation-specific renderers can consume the audit record later. Keeping
    acceptance separate from rendering makes undo/redo and frontend behavior
    deterministic while model backends are still optional.
    """

    def accept(
        self,
        history: DocumentHistory,
        proposal: PipelineProposal,
    ) -> tuple[Document, AcceptedProposal]:
        current = history.current
        record = AcceptedProposal(proposal.kind, proposal.name, proposal.to_dict()["proposal"])
        accepted = list(current.metadata.get("accepted_proposals", []))
        accepted.append(record.to_dict())
        updated = Document(
            document_id=current.document_id,
            sequence=current.sequence,
            layers=current.layers,
            edges=current.edges,
            metadata={**current.metadata, "accepted_proposals": accepted},
        )
        return history.commit(updated), record
