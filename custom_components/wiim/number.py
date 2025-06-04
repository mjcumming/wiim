"""WiiM number platform.

Provides configurable numeric settings that leverage the Speaker architecture
for device configuration and performance tuning.

Also provides group volume control for multiroom groups.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM number entities from a config entry.

    Creates group volume control entity that becomes available when
    the speaker acts as a multiroom group master.
    """
    speaker = get_speaker_from_config_entry(hass, config_entry)

    entities = [
        WiiMGroupVolumeControl(speaker),
    ]

    async_add_entities(entities)
    _LOGGER.info("Number platform setup complete for %s (%d entities)", speaker.name, len(entities))


class WiiMGroupVolumeControl(WiimEntity, NumberEntity):
    """Group volume control for WiiM multiroom groups.

    This entity provides synchronized volume control for all speakers
    in a multiroom group. It only becomes available when the speaker
    is acting as a group master with active group members.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0.0
    _attr_native_max_value = 1.0
    _attr_native_step = 0.01
    _attr_icon = "mdi:volume-high"
    _attr_entity_registry_enabled_default = False  # Start hidden

    def __init__(self, speaker: Speaker) -> None:
        """Initialize group volume control."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_group_volume"
        self._attr_name = "Group Volume"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        if self.speaker.role == "master" and self.speaker.group_members:
            member_names = [s.name for s in self.speaker.group_members if s != self.speaker]
            if len(member_names) == 1:
                return f"{self.speaker.name} + {member_names[0]} Group Volume"
            elif len(member_names) <= 3:
                return f"{self.speaker.name} + {len(member_names)} Speakers Group Volume"
            else:
                return f"{self.speaker.name} Group Volume ({len(member_names)} speakers)"
        return f"{self.speaker.name} Group Volume"

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Only available when speaker is master with active group members.
        """
        return self.speaker.available and self.speaker.role == "master" and len(self.speaker.group_members) > 0

    @property
    def native_value(self) -> float | None:
        """Return current group volume level."""
        if not self.available:
            return None

        # Return master's volume as group volume
        return self.speaker.get_volume_level()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.available:
            return {}

        return {
            "group_members": [s.name for s in self.speaker.group_members],
            "group_size": len(self.speaker.group_members),
            "master_device": self.speaker.name,
        }

    async def async_set_native_value(self, value: float) -> None:
        """Set group volume level."""
        if not self.available:
            _LOGGER.warning("Cannot set group volume - group not active")
            return

        _LOGGER.debug("Setting group volume to %.2f for %s", value, self.speaker.name)

        # Collect all volume change tasks
        tasks = []

        # Set master volume
        tasks.append(self._set_speaker_volume(self.speaker, value, "master"))

        # Set slave volumes
        for slave in self.speaker.group_members:
            if slave != self.speaker:  # Skip master (already included)
                tasks.append(self._set_speaker_volume(slave, value, "slave"))

        # Execute all volume changes simultaneously
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any failures
        successful = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                speaker_name = self.speaker.name if i == 0 else self.speaker.group_members[i - 1].name
                _LOGGER.warning("Failed to set volume for %s: %s", speaker_name, result)
            else:
                successful += 1

        _LOGGER.debug("Group volume set: %d/%d speakers successful", successful, len(results))

        # Refresh coordinator to update state
        await self._async_execute_command_with_refresh("group_volume_set")

    async def _set_speaker_volume(self, speaker: Speaker, volume: float, role: str) -> None:
        """Set volume for a specific speaker with error handling."""
        try:
            await speaker.coordinator.client.set_volume(volume)
            _LOGGER.debug("Set volume %.2f for %s (%s)", volume, speaker.name, role)
        except Exception as err:
            _LOGGER.debug("Failed to set volume for %s (%s): %s", speaker.name, role, err)
            raise  # Re-raise for gather() to handle
