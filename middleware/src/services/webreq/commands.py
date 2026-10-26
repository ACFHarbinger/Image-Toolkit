"""Command and result definitions for the WebRequests service (B-02 / #907)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class RequestItem:
    """A single request specification in a sequence."""

    type: Literal["GET", "POST", "PUT", "DELETE", "HEAD", "PATCH"] = "GET"
    param: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionItem:
    """An action to execute on HTTP response."""

    type: Literal[
        "Print Response URL",
        "Print Response Status Code",
        "Print Response Headers",
        "Print Response Content (Text)",
        "Save Response Content (Binary)",
    ] = "Print Response Status Code"
    param: str = ""


@dataclass(frozen=True)
class ExecuteCommand:
    """Command to execute a single HTTP request."""

    url: str
    method: Literal["GET", "POST", "PUT", "DELETE", "HEAD", "PATCH"] = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    timeout_seconds: int = 15


@dataclass(frozen=True)
class ExecuteResult:
    """Result of executing a single HTTP request."""

    url: str
    status_code: int
    status_text: str
    headers: dict[str, str]
    content_type: str
    body: str
    duration_ms: float
    error: str | None = None
    # Full response bytes. ``body`` is only a display preview.
    raw_body: bytes = b""


@dataclass(frozen=True)
class SequenceCommand:
    """Command to execute a sequential pipeline of HTTP requests."""

    base_url: str
    requests: list[RequestItem] = field(default_factory=list)
    actions: list[ActionItem] = field(default_factory=list)
    timeout_seconds: int = 15


@dataclass(frozen=True)
class SequenceItemResult:
    """Result of an individual request item within a sequence."""

    index: int
    url: str
    method: str
    status_code: int
    saved_path: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class SequenceResult:
    """Result of executing a sequential pipeline of HTTP requests."""

    status: Literal["completed", "failed", "cancelled"]
    base_url: str
    total_requests: int
    completed_requests: int
    logs: list[str]
    items: list[SequenceItemResult]
    message: str
