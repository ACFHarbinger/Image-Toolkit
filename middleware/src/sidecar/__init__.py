"""Python bridge sidecar (W0-12, #876).

The sidecar is intentionally small at startup: it imports only the shared
bridge package, its in-memory job registry and stdlib process plumbing. Heavy
service imports (Torch and friends) belong behind future service dispatchers.
"""

from middleware.src.sidecar.jobs import JobRecord, JobRegistry
from middleware.src.sidecar.server import SidecarServer

__all__ = ["JobRecord", "JobRegistry", "SidecarServer"]
