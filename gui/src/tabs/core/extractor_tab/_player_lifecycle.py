"""Explicit lifecycle state for the extractor tab's internal video player
(ui-arch-43 / R2.d, issue #565).

Replaces the implicit "is the player built yet / did the right signal
fire" reasoning ``load_media()``/``toggle_playback()`` used to rely on
with one named, logged state per active video:

``NotLoaded -> Restored -> PlayerReady -> Playing``

``Restored`` is a session-recovery deferred load (issue #81 crash family:
constructing ``QMediaPlayer``/spawning the storyboard subprocess during
the startup burst, with the JVM loaded, reliably aborts) -- UI state
(active tab, video path, per-video config) is set, but the player and
storyboard stay unconstructed until the first real interaction.

The ``PlayerReady`` transition is also where issue #546's real remaining
bug lived: ``QGraphicsVideoItem.nativeSizeChanged`` only fires on an
actual *value change* -- reusing the same item across videos, swapping to
a same-resolution video left a stale fit from the previous one, with
nothing to re-trigger it. Every entry into ``PlayerReady`` now
unconditionally calls ``fit_video_in_view()`` instead of relying on that
signal, closing the gap regardless of whether the new video's native size
happens to differ from the old one's.
"""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING, Optional

from ._tab_bound import TabBoundController

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol

logger = logging.getLogger(__name__)


class PlayerLifecycleState(enum.Enum):
    """One active video's lifecycle. Never shared across videos -- switching
    the active tab re-enters at ``NotLoaded`` (or ``Restored``, if the new
    tab itself was a deferred session-recovery load)."""

    NOT_LOADED = "not_loaded"
    RESTORED = "restored"
    PLAYER_READY = "player_ready"
    PLAYING = "playing"


class ExtractorPlayerLifecycleController(TabBoundController):
    """Owns the current :class:`PlayerLifecycleState` and its transitions."""

    _player_lifecycle_state: PlayerLifecycleState = PlayerLifecycleState.NOT_LOADED

    def _set_player_lifecycle_state(
        self: "VideoExtractorSubTabHostProtocol",
        new_state: PlayerLifecycleState,
        *,
        video_path: Optional[str] = None,
    ) -> None:
        old_state = getattr(self, "_player_lifecycle_state", PlayerLifecycleState.NOT_LOADED)
        self._player_lifecycle_state = new_state
        if old_state is new_state:
            return
        logger.info(
            "[player-lifecycle] %s -> %s (video=%s)",
            old_state.value,
            new_state.value,
            video_path if video_path is not None else getattr(self, "video_path", None),
        )
        if new_state is PlayerLifecycleState.PLAYER_READY:
            # Unconditional, not signal-gated: see module docstring (#546).
            self.fit_video_in_view()


__all__ = ["PlayerLifecycleState", "ExtractorPlayerLifecycleController"]
