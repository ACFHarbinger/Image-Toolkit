"""Stateful orchestration session shared by embedded and standalone hosts."""

from __future__ import annotations

from typing import Any

from document import Document, DocumentHistory
from .acceptance import AcceptedProposal, ProposalAcceptanceService
from .defaults import build_default_pipeline
from .orchestrator import PipelineProposal, ProposalPipeline
from .restoration import RestorationPipeline
from jobs import RestorationResult
from jobs.base import JobHandle


class PipelineSession:
    """Own the active document history and proposal registry for one editor."""

    def __init__(
        self,
        document: Document,
        *,
        pipeline: ProposalPipeline | None = None,
        restoration: RestorationPipeline | None = None,
    ) -> None:
        self.history = DocumentHistory(document)
        self.pipeline = pipeline if pipeline is not None else build_default_pipeline()
        self.restoration = restoration if restoration is not None else RestorationPipeline()
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

    def submit_restoration(
        self,
        operation: str,
        input_ref: str,
        *,
        backend: str = "pillow",
        options: dict[str, Any] | None = None,
    ) -> JobHandle[RestorationResult]:
        """Submit a cancellable restoration preview for the active editor session."""
        return self.restoration.submit(
            operation, input_ref, backend=backend, options=options
        )
