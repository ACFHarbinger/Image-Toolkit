"""Small serializable contracts shared by both HIE frontends."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EditRequest:
    """A deterministic request to apply one named operation to a document."""

    operation: str
    document_id: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationResult:
    """Result envelope suitable for JSON/IPC serialization."""

    request_id: str
    status: str
    output_document_id: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "output_document_id": self.output_document_id,
            "error": self.error,
        }
