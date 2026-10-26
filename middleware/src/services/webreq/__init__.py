"""WebRequests service package (B-02 / #907)."""

from middleware.src.services.webreq.commands import (
    ActionItem,
    ExecuteCommand,
    ExecuteResult,
    RequestItem,
    SequenceCommand,
    SequenceItemResult,
    SequenceResult,
)
from middleware.src.services.webreq.handlers import ExecuteHandler, SequenceHandler
from middleware.src.services.webreq.protocols import WebRequestsServiceProtocol
from middleware.src.services.webreq.service import WebRequestsService

__all__ = [
    "ActionItem",
    "ExecuteCommand",
    "ExecuteResult",
    "ExecuteHandler",
    "RequestItem",
    "SequenceCommand",
    "SequenceItemResult",
    "SequenceResult",
    "SequenceHandler",
    "WebRequestsServiceProtocol",
    "WebRequestsService",
]
