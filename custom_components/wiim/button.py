"""WiiM button platform.

Provides useful device maintenance buttons. All buttons are optional and only
created when maintenance buttons are enabled in options.
"""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM maintenance buttons from a config entry.

    Only creates useful maintenance buttons that users actually need.
    All buttons are optional and controlled by user preferences.
    """
    speaker = get_speaker_from_config_entry(hass, config_entry)
    entry = hass.data["wiim"][config_entry.entry_id]["entry"]

    entities = []
    # Only create maintenance buttons if the option is enabled
    if entry.options.get("enable_maintenance_buttons", False):
        entities.extend(
            [
                WiiMRebootButton(speaker),
                WiiMSyncTimeButton(speaker),
            ]
        )

    # Bluetooth scan is now integrated into Audio Output Mode select (BT Scan option)
    # No separate Bluetooth scan button needed

    async_add_entities(entities)
    _LOGGER.info("Created %d button entities for %s", len(entities), speaker.name)


class WiiMRebootButton(WiimEntity, ButtonEntity):
    """Device reboot button for system maintenance.

    Useful for resolving connectivity issues or applying firmware updates.
    """

    _attr_icon = "mdi:restart"

    def __init__(self, speaker: Speaker) -> None:
        """Initialize reboot button."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_reboot"
        self._attr_name = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self.speaker.name} Reboot"  # Display name includes action

    async def async_press(self) -> None:
        """Execute device reboot command.

        Sends reboot command to the device and requests status refresh
        to monitor the reboot process.
        """
        try:
            _LOGGER.info("Initiating reboot for %s", self.speaker.name)
            await self.speaker.coordinator.player.client.reboot()
            _LOGGER.info("Reboot command sent successfully to %s", self.speaker.name)
            await self._async_execute_command_with_refresh("reboot")

        except Exception as err:
            # Reboot commands often don't return proper responses
            # Log the attempt but don't fail the button press
            _LOGGER.info(
                "Reboot command sent to %s (device may not respond): %s",
                self.speaker.name,
                err,
            )
            # Don't raise - reboot command was sent successfully
            # The device will reboot even if the response parsing fails
            await self._async_execute_command_with_refresh("reboot")


class WiiMSyncTimeButton(WiimEntity, ButtonEntity):
    """Device time synchronization button.

    Synchronizes the device clock with network time for accurate timestamps.
    """

    _attr_icon = "mdi:clock-sync"

    def __init__(self, speaker: Speaker) -> None:
        """Initialize time sync button."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_sync_time"
        self._attr_name = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self.speaker.name} Sync Time"  # Display name includes action

    async def async_press(self) -> None:
        """Execute time synchronization command.

        Synchronizes the device's internal clock with network time,
        ensuring accurate timestamps for media metadata and logs.
        """
        try:
            _LOGGER.info("Synchronizing time for %s", self.speaker.name)
            await self.speaker.coordinator.player.client.sync_time()
            await self._async_execute_command_with_refresh("sync_time")

        except Exception as err:
            _LOGGER.error("Failed to sync time for %s: %s", self.speaker.name, err)
            raise


class WiiMBluetoothScanButton(WiimEntity, ButtonEntity):
    """Bluetooth device scan button.

    Initiates a Bluetooth device discovery scan to find nearby devices
    that can be paired and connected.
    """

    _attr_icon = "mdi:bluetooth-search"

    def __init__(self, speaker: Speaker) -> None:
        """Initialize Bluetooth scan button."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_bluetooth_scan"
        self._attr_name = None
        self._scan_in_progress = False

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self.speaker.name} Bluetooth Scan"

    @property
    def available(self) -> bool:
        """Return if the button is available (not scanning)."""
        # Disable button during scan to prevent multiple simultaneous scans
        # Read directly from coordinator data
        scan_status = self.coordinator.data.get("bt_scan_status", "Idle") if self.coordinator.data else "Idle"
        is_scanning = scan_status in ("Scanning", "Initializing") or self._scan_in_progress
        return not is_scanning

    async def async_press(self) -> None:
        """Execute Bluetooth device scan.

        Scans for nearby Bluetooth devices and stores results for selection.
        """
        # Prevent multiple simultaneous scans
        # Read directly from coordinator data
        scan_status = self.coordinator.data.get("bt_scan_status", "Idle") if self.coordinator.data else "Idle"
        if scan_status in ("Scanning", "Initializing") or self._scan_in_progress:
            _LOGGER.warning(
                "Bluetooth scan already in progress for %s (status: %s). Please wait for current scan to complete.",
                self.speaker.name,
                scan_status,
            )
            return

        try:
            self._scan_in_progress = True
            self.async_write_ha_state()  # Update button state to show it's disabled

            _LOGGER.info("Starting Bluetooth scan for %s", self.speaker.name)
            # Update coordinator data to show scanning state
            if self.coordinator.data:
                self.coordinator.data["bt_scan_status"] = "Scanning"
                self.coordinator.data["bt_history"] = []

            # Trigger entity update to show scanning state
            self.async_write_ha_state()

            # Perform the scan (10 seconds for better device discovery) - pywiim handles this
            devices = await self.speaker.coordinator.player.client.scan_for_bluetooth_devices(duration=10)

            # Log detailed scan results
            _LOGGER.info(
                "Bluetooth scan completed for %s: found %d devices",
                self.speaker.name,
                len(devices),
            )
            if devices:
                for i, device in enumerate(devices, 1):
                    _LOGGER.info(
                        "  Device %d: name='%s', mac='%s', rssi=%s",
                        i,
                        device.get("name", "Unknown"),
                        device.get("mac", "N/A"),
                        device.get("rssi", "N/A"),
                    )
            else:
                _LOGGER.warning(
                    "No Bluetooth devices found during scan for %s. "
                    "Make sure Bluetooth devices are in pairing mode and nearby.",
                    self.speaker.name,
                )

            # Store results in coordinator data
            _LOGGER.info(
                "Storing %d Bluetooth devices for %s: %s",
                len(devices),
                self.speaker.name,
                [f"{d.get('name', 'Unknown')} ({d.get('mac', 'N/A')})" for d in devices] if devices else "none",
            )
            # Update coordinator data with scan results
            if self.coordinator.data:
                self.coordinator.data["bt_history"] = devices
                self.coordinator.data["bt_scan_status"] = "Complete"
            # Request refresh to propagate changes
            await self.coordinator.async_request_refresh()

            # Verify storage - read from coordinator data
            stored = self.coordinator.data.get("bt_history", []) if self.coordinator.data else []
            _LOGGER.info(
                "Verified stored devices for %s: %d devices found",
                self.speaker.name,
                len(stored),
            )

            # Trigger entity update to show results
            self.async_write_ha_state()

            # Also trigger update on any select entities that might be listening
            async_dispatcher_send(
                self.hass,
                f"wiim_bluetooth_scan_complete_{self.speaker.uuid}",
            )

        except Exception as err:
            _LOGGER.error("Failed to scan Bluetooth devices for %s: %s", self.speaker.name, err)
            # Update coordinator data to show failed state
            if self.coordinator.data:
                self.coordinator.data["bt_scan_status"] = "Failed"
                self.coordinator.data["bt_history"] = []
            raise
        finally:
            # Always re-enable button after scan completes (success or failure)
            self._scan_in_progress = False
            self.async_write_ha_state()
