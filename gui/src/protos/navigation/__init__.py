"""Navigation components for the modular shell (§2.36)."""

from .navigation_rail import NavigationRailWidget
from .segmented_ribbon import TopSegmentedRibbonWidget
from .shell_manager import ShellLayoutManager, ShellNavMode

__all__ = [
    "NavigationRailWidget",
    "TopSegmentedRibbonWidget",
    "ShellLayoutManager",
    "ShellNavMode",
]
