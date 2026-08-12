"""Stateful orchestration session shared by embedded and standalone hosts."""

from __future__ import annotations

from typing import Any

from ..document import Document, DocumentHistory
from .acceptance import AcceptedProposal, ProposalAcceptanceService
from .defaults import build_default_pipeline
from .orchestrator import PipelineProposal, ProposalPipeline


class PipelineSession:
    """Own the active document history and proposal registry for one editor."""

    def __init__(
        self,
        document: Document,
        *,
        pipeline: ProposalPipeline | None = None,
    ) -> None:
        self.history = DocumentHistory(document)
        self.pipeline = pipeline if pipeline is not None else build_default_pipeline()
        self._acceptance = ProposalAcceptanceService()

    @property
    def document(self) -> Document:
        return self.history.current

    def preview_policy(self, name: str, observation: dict[str, Any]) -> PipelineProposal:
        """Create an inspectable policy proposal without changing the document."""
        return self.pipeline.policy_proposal(name, observation)

    def accept(self, proposal: PipelineProposal) -> AcceptedProposal:
        """Explicitly accept a proposal and record it in undoable history."""
        _, record = self._acceptance.accept(self.history, proposal)
        return record
