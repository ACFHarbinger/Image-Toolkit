"""Process supervisor for the Tauri/PySide6 desktop (issue #877 / W0-13).

The supervisor runs outside the webview and starts the sidecar, Cloud Jobs
daemon and slideshow daemon as siblings. Fake children stand in until
#875/#876 land. Closing the GUI does not stop durable siblings; a sidecar
crash emits ``bridge.down`` then ``bridge.ready`` without touching daemon
PIDs.
"""

from middleware.src.supervisor.autostart import disable as disable_autostart
from middleware.src.supervisor.autostart import enable as enable_autostart
from middleware.src.supervisor.autostart import is_enabled as autostart_enabled
from middleware.src.supervisor.envelope import (
    BRIDGE_DOWN,
    BRIDGE_READY,
    PROTOCOL_VERSION,
    BridgeEvent,
    ErrorEnvelope,
)
from middleware.src.supervisor.gui_gate import GuiInstance
from middleware.src.supervisor.gui_shell import claim_or_focus
from middleware.src.supervisor.supervisor import Supervisor

__all__ = [
    "PROTOCOL_VERSION",
    "BRIDGE_DOWN",
    "BRIDGE_READY",
    "BridgeEvent",
    "ErrorEnvelope",
    "GuiInstance",
    "Supervisor",
    "claim_or_focus",
    "autostart_enabled",
    "disable_autostart",
    "enable_autostart",
]
