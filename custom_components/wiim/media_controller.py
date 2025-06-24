"""WiiM Media Player Controller - Main Facade.

This is the main controller facade that combines all media player functionality through mixins:
- MediaControllerCoreMixin: Volume, playback, source control
- MediaControllerGroupMixin: Group management and entity resolution
- MediaControllerMediaMixin: Media metadata, image handling, advanced features

Refactored from a monolithic controller (886 LOC) into focused modules following
natural code boundaries. This facade provides a clean public interface while
delegating to specialized mixins.

Following the successful API refactor pattern with logical cohesion over arbitrary size limits.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .media_controller_core import MediaControllerCoreMixin
from .media_controller_group import MediaControllerGroupMixin
from .media_controller_media import MediaControllerMediaMixin

if TYPE_CHECKING:
    from .data import Speaker

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "MediaPlayerController",
]


class MediaPlayerController(
    MediaControllerCoreMixin,
    MediaControllerGroupMixin,
    MediaControllerMediaMixin,
):
    """Single controller handling ALL media player complexity through focused mixins.

    This controller facade combines:
    - Volume management with master/slave coordination (CoreMixin)
    - Playback control with group awareness (CoreMixin)
    - Source selection with EQ and mode management (CoreMixin)
    - Group operations with validation and state sync (GroupMixin)
    - Media metadata and artwork handling (MediaMixin)
    - Advanced features like preset/URL playback (MediaMixin)

    Each mixin handles a specific domain of functionality, promoting maintainability
    and testability while presenting a unified interface to the media player entity.
    """

    def __init__(self, speaker: Speaker) -> None:
        """Initialize the media player controller with all mixins.

        Args:
            speaker: The Speaker instance this controller manages
        """
        # Initialize core functionality first (sets up common attributes)
        MediaControllerCoreMixin.__init__(self, speaker)

        # Initialize media handling (sets up image caching)
        MediaControllerMediaMixin.__init__(self)

        # Group mixin has no additional initialization

        self._logger.debug(
            "MediaPlayerController facade initialized for %s with %d mixins",
            speaker.name,
            3,  # CoreMixin + GroupMixin + MediaMixin
        )
