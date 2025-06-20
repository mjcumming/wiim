"""WiiM switch platform.

Provides audio feature toggles when EQ controls are enabled.
Also provides group mute control for multiroom groups.
Only creates switches for user-facing audio features.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_EQ_CONTROLS, DOMAIN, EQ_PRESET_MAP
from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM switches with filtering.

    Creates EQ switch when EQ controls are enabled and group mute control
    for multiroom group management.
    """
    speaker = get_speaker_from_config_entry(hass, config_entry)
    entry = hass.data[DOMAIN][config_entry.entry_id]["entry"]

    entities = []

    # Only create equalizer switch when EQ controls are enabled
    if entry.options.get(CONF_ENABLE_EQ_CONTROLS, False):
        entities.append(WiiMEqualizerSwitch(speaker))

    # Always create group mute control (becomes available when needed)
    entities.append(WiiMGroupMuteControl(speaker))

    async_add_entities(entities)
    _LOGGER.info("Created %d switch entities for %s (filtering applied)", len(entities), speaker.name)


class WiiMGroupMuteControl(WiimEntity, SwitchEntity):
    """Group mute control for WiiM multiroom groups.

    Provides synchronized mute control for all speakers in a multiroom group.
    Only becomes available when the speaker is acting as a group master.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:volume-off"
    # Enabled by default so the entity is visible immediately. Availability
    # is still driven by the `available` property (only when this speaker is
    # group master).
    _attr_entity_registry_enabled_default = True

    def __init__(self, speaker: Speaker) -> None:
        """Initialize group mute control."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_group_mute"
        self._attr_name = "Group Mute"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        if self.speaker.role == "master" and self.speaker.group_members:
            member_names = [s.name for s in self.speaker.group_members if s != self.speaker]
            if len(member_names) == 1:
                return f"{self.speaker.name} + {member_names[0]} Group Mute"
            elif len(member_names) <= 3:
                return f"{self.speaker.name} + {len(member_names)} Speakers Group Mute"
            else:
                return f"{self.speaker.name} Group Mute ({len(member_names)} speakers)"
        return f"{self.speaker.name} Group Mute"

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Only available when speaker is master.
        """
        return self.speaker.available and self.speaker.role == "master"

    @property
    def is_on(self) -> bool | None:
        """Return *group* mute state.

        The switch is considered ON only when **every** member of the group
        explicitly reports muted.
        """
        if not self.available:
            return None

        # Collect mute states for master and slaves. Treat "unknown" (None)
        # as *not muted* so that missing data won't leave the switch in an
        # indeterminate state.  The group is muted only when **every** member
        # explicitly reports muted.

        mute_states: list[bool] = []

        for spk in [self.speaker] + self.speaker.group_members:
            state = spk.is_volume_muted()
            mute_states.append(state is True)  # None → False, False → False, True → True

        return all(mute_states)

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

    async def async_turn_on(self, **kwargs) -> None:
        """Mute entire group."""
        await self._set_group_mute(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Unmute entire group."""
        await self._set_group_mute(False)

    async def _set_group_mute(self, mute: bool) -> None:
        """Set mute state for entire group."""
        if not self.available:
            _LOGGER.warning("Cannot set group mute - group not active")
            return

        _LOGGER.debug("Setting group mute to %s for %s", mute, self.speaker.name)

        # Collect all mute change tasks
        tasks = []

        # Set master mute
        tasks.append(self._set_speaker_mute(self.speaker, mute, "master"))

        # Set slave mutes
        for slave in self.speaker.group_members:
            if slave != self.speaker:  # Skip master
                tasks.append(self._set_speaker_mute(slave, mute, "slave"))

        # Execute all mute changes simultaneously
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any failures
        successful = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                speaker_name = self.speaker.name if i == 0 else self.speaker.group_members[i - 1].name
                _LOGGER.warning("Failed to set mute for %s: %s", speaker_name, result)
            else:
                successful += 1

        _LOGGER.debug("Group mute set: %d/%d speakers successful", successful, len(results))

        # Refresh coordinator to update state
        await self._async_execute_command_with_refresh("group_mute_set")

    async def _set_speaker_mute(self, speaker: Speaker, mute: bool, role: str) -> None:
        """Set mute for a specific speaker with error handling."""
        try:
            await speaker.coordinator.client.set_mute(mute)
            _LOGGER.debug("Set mute %s for %s (%s)", mute, speaker.name, role)
        except Exception as err:
            _LOGGER.debug("Failed to set mute for %s (%s): %s", speaker.name, role, err)
            raise  # Re-raise for gather() to handle


class WiiMEqualizerSwitch(WiimEntity, SwitchEntity):
    """Equalizer enable/disable switch for audio enhancement control.

    Only created when EQ controls are enabled.
    Allows users to toggle the device's built-in equalizer system.
    """

    _attr_icon = "mdi:equalizer"

    def __init__(self, speaker: Speaker) -> None:
        """Initialize equalizer switch."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_equalizer"
        self._attr_name = "Equalizer"  # Generic label
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool | None:
        """Return true if equalizer is enabled."""
        if not self.speaker.coordinator.data:
            return None

        eq_info = self.speaker.coordinator.data.get("eq", {})
        return bool(eq_info.get("enabled", False))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the equalizer.

        Activates the device's built-in equalizer system, allowing audio
        enhancement through preset or custom EQ curves.
        """
        try:
            _LOGGER.info("Enabling equalizer for %s", self.speaker.name)
            await self.speaker.coordinator.client.set_eq_enabled(True)
            await self._async_execute_command_with_refresh("equalizer_on")

        except Exception as err:
            _LOGGER.error("Failed to enable equalizer for %s: %s", self.speaker.name, err)
            raise

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the equalizer.

        Deactivates the device's equalizer system, returning to flat
        frequency response for unprocessed audio output.
        """
        try:
            _LOGGER.info("Disabling equalizer for %s", self.speaker.name)
            await self.speaker.coordinator.client.set_eq_enabled(False)
            await self._async_execute_command_with_refresh("equalizer_off")

        except Exception as err:
            _LOGGER.error("Failed to disable equalizer for %s: %s", self.speaker.name, err)
            raise

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return equalizer-related information."""
        if not self.speaker.coordinator.data:
            return {"eq_supported": False, "current_preset": None, "available_presets": []}

        eq_info = self.speaker.coordinator.data.get("eq", {})
        polling_info = self.speaker.coordinator.data.get("polling", {})
        api_capabilities = polling_info.get("api_capabilities", {})

        attrs = {
            "eq_supported": api_capabilities.get("eq_supported", False),
            "current_preset": eq_info.get("eq_preset"),
            "available_presets": list(EQ_PRESET_MAP.keys()),
        }

        return attrs
