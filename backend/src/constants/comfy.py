"""Independent ComfyUI service and browser-view states (#736)."""
from enum import StrEnum


class ServerState(StrEnum):
    STOPPED = "Stopped"
    STARTING = "Starting"
    READY = "Ready"
    DISCONNECTED = "Disconnected"


class ViewState(StrEnum):
    NOT_CREATED = "NotCreated"
    LOADING = "Loading"
    DISPLAYED = "Displayed"
    RENDERER_FAILED = "RendererFailed"


class RunStatus(StrEnum):
    """Lifecycle of a captured ComfyUI prompt run (#737)."""

    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    INTERRUPTED = "Interrupted"
