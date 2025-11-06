"""Select entities for WiiM integration."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# from .const import DOMAIN
from .data import Speaker, get_speaker_from_config_entry
from .entity import WiimEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiiM select entities."""
    speaker = get_speaker_from_config_entry(hass, config_entry)

    entities = []

    # Determine capabilities safely. Prefer client.capabilities if it is a dict,
    # otherwise use coordinator._capabilities if it is a dict. Avoid treating
    # MagicMock attributes as truthy capability containers.
    capabilities = None

    client = getattr(speaker.coordinator, "client", None)
    client_capabilities = getattr(client, "capabilities", None)
    if isinstance(client_capabilities, dict):
        capabilities = client_capabilities
    else:
        coordinator_capabilities = getattr(speaker.coordinator, "_capabilities", None)
        if isinstance(coordinator_capabilities, dict):
            capabilities = coordinator_capabilities

    if isinstance(capabilities, dict):
        supports_audio_output = bool(capabilities.get("supports_audio_output", False))
        if supports_audio_output:
            # Audio Output Mode Select
            entities.append(WiiMOutputModeSelect(speaker))
            _LOGGER.debug(
                "Creating audio output select entity - device supports audio output"
            )
        else:
            _LOGGER.debug(
                "Skipping audio output select entity - device does not support audio output (capability=%s)",
                supports_audio_output,
            )
    else:
        # Fallback: create entity if capabilities not available (assume supported for backwards compatibility)
        _LOGGER.warning(
            "Capabilities not available for %s - creating audio output select entity as fallback",
            speaker.name,
        )
        entities.append(WiiMOutputModeSelect(speaker))

    # Bluetooth device selection is now integrated into Audio Output Mode select
    # No separate Bluetooth device select entity needed

    async_add_entities(entities)
    _LOGGER.info(
        "Created %d select entities for %s",
        len(entities),
        speaker.name,
    )


class WiiMOutputModeSelect(WiimEntity, SelectEntity):
    """Select entity for audio output mode control."""

    _attr_icon = "mdi:audio-video"
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_output_mode"
        self._attr_name = "Audio Output Mode"

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        try:
            # Check if core device communication is working
            if (
                hasattr(self.speaker.coordinator, "_device_info_working")
                and not self.speaker.coordinator._device_info_working
            ):
                # Device communication is failing - return None to show as unavailable
                # This indicates a device connectivity issue rather than audio output issue
                return None

            current_mode = self.speaker.get_current_output_mode()

            # If Bluetooth output is active, show the connected device instead of just "Bluetooth Out"
            if (
                current_mode == "Bluetooth Out"
                and self.speaker.is_bluetooth_output_active()
            ):
                connected_device = self.speaker.get_connected_bluetooth_device()
                if connected_device:
                    device_name = connected_device.get("name", "Unknown")
                    # Find the device index in history to match "BT Device X - Name" format
                    bt_history = self.speaker.get_bluetooth_history()
                    for idx, device in enumerate(bt_history, start=1):
                        if device.get("name") == device_name:
                            return f"BT Device {idx} - {device_name}"
                    # Fallback: if not found in history, just show device name
                    return f"BT Device - {device_name}"

            return current_mode
        except Exception:
            # Return None if we can't determine the current option
            # This will show as "unknown" in the UI instead of "unavailable"
            _LOGGER.debug(
                "Could not determine current audio output mode for %s",
                self.speaker.name,
            )
            return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator updates - ensure entity state is refreshed when bt_history changes."""
        super()._handle_coordinator_update()
        # Force state write to ensure options and current_option are re-evaluated
        # This is important because options depends on coordinator data (bt_history)
        self.async_write_ha_state()

    @property
    def options(self) -> list[str]:
        """Return a list of available options."""
        try:
            # Get standard selectable modes (excluding Bluetooth Out - we'll add device-specific options)
            standard_modes = self.speaker.get_output_mode_list()

            # Get any discovered modes from the device
            discovered_modes = self.speaker.get_discovered_output_modes()

            # Combine and deduplicate, but exclude "Bluetooth Out" (we'll add device-specific options)
            all_modes = list(set(standard_modes + discovered_modes))
            all_modes = [m for m in all_modes if m != "Bluetooth Out"]

            # Get Bluetooth devices from history (already paired devices)
            # Users pair devices via the WiiM app - we just show the list and allow connection
            bt_history = self.speaker.get_bluetooth_history()
            # Ensure bt_history is a list (can be None if not fetched yet)
            if not bt_history or not isinstance(bt_history, list):
                bt_history = []
                _LOGGER.debug(
                    "No Bluetooth history available for %s yet (options will update when history is fetched)",
                    self.speaker.name,
                )
            else:
                _LOGGER.debug(
                    "Found %d Bluetooth devices in history for %s: %s",
                    len(bt_history),
                    self.speaker.name,
                    [d.get("name", "Unknown") for d in bt_history[:5]],
                )
            bt_options = []

            # Add option to refresh paired devices list (user may have paired new device via WiiM app)
            bt_options.append("BT Update Paired Devices")

            # Add each device from history as "BT Device X - Name"
            # Only show devices that have been paired (no scan needed - pairing happens in WiiM app)
            for idx, device in enumerate(bt_history, start=1):
                device_name = device.get("name", "Unknown Device")
                mac = device.get("ad", "") or device.get("mac", "")
                if device_name and mac:
                    # Format: "BT Device 1 - TOZO-T6" or "BT Device 2 - DELL27KITCHEN"
                    bt_options.append(f"BT Device {idx} - {device_name}")

            # Sort standard modes, then append BT options
            all_modes_sorted = sorted(all_modes)
            all_modes_sorted.extend(bt_options)

            return all_modes_sorted
        except Exception:
            # If we can't determine available options, return basic modes
            # This prevents the entity from becoming unavailable
            _LOGGER.debug(
                "Could not determine audio output options for %s, using defaults",
                self.speaker.name,
            )
            from .const import SELECTABLE_OUTPUT_MODES

            return SELECTABLE_OUTPUT_MODES.copy()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        _LOGGER.info("WiiM Output Mode Select: User selected '%s'", option)
        try:
            # Handle special Bluetooth options
            # Update paired devices list (refresh from WiiM device)
            if option == "BT Update Paired Devices":
                _LOGGER.info(
                    "Updating Bluetooth paired devices list for %s", self.speaker.name
                )

                # Fetch fresh Bluetooth history from device
                async def _refresh_and_update():
                    try:
                        # Fetch fresh BT history
                        fresh_history = await self.speaker.coordinator.client.get_bluetooth_history()
                        _LOGGER.info(
                            "Bluetooth history updated for %s: %d devices found",
                            self.speaker.name,
                            len(fresh_history)
                            if isinstance(fresh_history, list)
                            else 0,
                        )
                        # Update coordinator data with fresh history
                        if self.coordinator.data:
                            self.coordinator.data["bt_history"] = fresh_history
                        # Refresh coordinator to propagate changes
                        await self.coordinator.async_request_refresh()
                        # Refresh entity state to update options dropdown
                        self.async_write_ha_state()
                    except Exception as refresh_err:
                        _LOGGER.error(
                            "Failed to update Bluetooth devices list for %s: %s",
                            self.speaker.name,
                            refresh_err,
                        )

                # Start refresh in background
                if hasattr(self, "hass") and self.hass:
                    self.hass.async_create_task(_refresh_and_update())
                else:
                    import asyncio

                    _ = asyncio.create_task(
                        _refresh_and_update()
                    )  # Store reference to avoid warning
                _LOGGER.info(
                    "Bluetooth devices list refresh initiated for %s. Options will update after refresh completes.",
                    self.speaker.name,
                )
                return

            # Handle "BT Device X - Name" format
            if option.startswith("BT Device "):
                # Extract device name from "BT Device X - Name"
                # Find the device index or name
                device_name = option.split(" - ", 1)[-1] if " - " in option else None

                # Get Bluetooth history to find the device
                bt_history = self.speaker.get_bluetooth_history()
                mac_address = None

                for device in bt_history:
                    if device.get("name") == device_name:
                        mac_address = device.get("ad", "") or device.get("mac", "")
                        break

                if not mac_address:
                    _LOGGER.error(
                        "Could not find MAC address for Bluetooth device '%s'",
                        device_name,
                    )
                    raise ValueError(
                        f"Bluetooth device '{device_name}' not found in history"
                    )

                # Store current output mode before attempting connection (for revert on failure)
                previous_output_mode = self.speaker.get_current_output_mode()
                _LOGGER.info(
                    "Connecting to Bluetooth device %s (%s) and setting output mode to Bluetooth (current mode: %s)",
                    device_name,
                    mac_address,
                    previous_output_mode,
                )

                try:
                    # Connect to the device
                    await self.speaker.coordinator.client.connect_bluetooth_device(
                        mac_address
                    )

                    # Set output mode to Bluetooth Out
                    from .media_controller import MediaPlayerController

                    controller = MediaPlayerController(self.speaker)
                    await controller.select_output_mode("Bluetooth Out")

                    _LOGGER.info(
                        "Successfully connected to Bluetooth device %s and set output mode to Bluetooth",
                        device_name,
                    )

                    # Refresh coordinator to get updated status
                    await self.coordinator.async_request_refresh()
                except Exception as bt_err:
                    # Bluetooth connection failed - revert to previous output mode
                    _LOGGER.error(
                        "Bluetooth connection to %s (%s) failed: %s. Reverting to previous output mode: %s",
                        device_name,
                        mac_address,
                        bt_err,
                        previous_output_mode,
                    )

                    if previous_output_mode and previous_output_mode != "Bluetooth Out":
                        try:
                            from .media_controller import MediaPlayerController

                            controller = MediaPlayerController(self.speaker)
                            await controller.select_output_mode(previous_output_mode)
                            _LOGGER.info(
                                "Reverted output mode to %s after Bluetooth connection failure",
                                previous_output_mode,
                            )
                        except Exception as revert_err:
                            _LOGGER.error(
                                "Failed to revert output mode to %s: %s",
                                previous_output_mode,
                                revert_err,
                            )
                    else:
                        # If no previous mode or it was already Bluetooth, default to Line Out
                        try:
                            from .media_controller import MediaPlayerController

                            controller = MediaPlayerController(self.speaker)
                            await controller.select_output_mode("Line Out")
                            _LOGGER.info(
                                "Reverted output mode to Line Out (default) after Bluetooth connection failure"
                            )
                        except Exception as revert_err:
                            _LOGGER.error(
                                "Failed to revert output mode to Line Out: %s",
                                revert_err,
                            )

                    # Refresh coordinator and re-raise the original exception
                    await self.coordinator.async_request_refresh()
                    raise

                return

            # Handle regular output modes (Line Out, Optical Out, etc.)
            from .media_controller import MediaPlayerController

            controller = MediaPlayerController(self.speaker)
            _LOGGER.info(
                "WiiM Output Mode Select: Calling select_output_mode('%s')", option
            )
            await controller.select_output_mode(option)
            _LOGGER.info(
                "WiiM Output Mode Select: Successfully set output mode to '%s'",
                option,
            )
        except ValueError:
            # Re-raise ValueError (validation errors) - these should propagate
            raise
        except Exception as err:
            _LOGGER.warning(
                "WiiM Output Mode Select: Failed to select output mode '%s': %s",
                option,
                err,
            )
            # Don't re-raise other exceptions - let Home Assistant handle them
            # This prevents the entity from becoming unavailable

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        try:
            bt_history = self.speaker.get_bluetooth_history()
            # Ensure bt_history is a list (can be None if not fetched yet)
            if not bt_history or not isinstance(bt_history, list):
                bt_device_count = 0
            else:
                bt_device_count = len(
                    [d for d in bt_history if d.get("ad") or d.get("mac")]
                )
        except Exception:
            bt_device_count = 0

        return {
            "bluetooth_output_active": self.speaker.is_bluetooth_output_active(),
            "audio_cast_active": self.speaker.is_audio_cast_active(),
            "discovered_modes": self.speaker.get_discovered_output_modes(),
            "bluetooth_devices_available": bt_device_count,
            "bluetooth_pairing_note": "Pair devices via WiiM app, then use 'BT Update Paired Devices' to refresh",
        }


class WiiMBluetoothDeviceSelect(WiimEntity, SelectEntity):
    """Select entity for choosing and connecting to Bluetooth devices."""

    _attr_icon = "mdi:bluetooth"
    _attr_has_entity_name = True

    def __init__(self, speaker: Speaker) -> None:
        """Initialize Bluetooth device select entity."""
        super().__init__(speaker)
        self._attr_unique_id = f"{speaker.uuid}_bluetooth_device"
        self._attr_name = "Bluetooth Device"
        self._connected_device_mac: str | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator updates - ensure entity state is refreshed."""
        super()._handle_coordinator_update()
        # Force state write to ensure current_option is re-evaluated
        # This is important because current_option depends on coordinator data (bt_history)
        _LOGGER.debug(
            "Coordinator update received for Bluetooth device select %s, refreshing state",
            self.speaker.name,
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Set up entity and listen for scan completion."""
        await super().async_added_to_hass()

        # Load Bluetooth history (previously paired devices) on startup
        try:
            _LOGGER.debug("Loading Bluetooth history for %s", self.speaker.name)
            history = await self.speaker.coordinator.client.get_bluetooth_history()
            if history:
                _LOGGER.info(
                    "Loaded %d previously paired Bluetooth devices for %s",
                    len(history),
                    self.speaker.name,
                )
                # Merge with existing devices (if any) and store
                existing = self.speaker.get_bluetooth_devices()
                # Create a dict keyed by MAC to avoid duplicates
                device_map: dict[str, dict[str, Any]] = {}
                for device in existing:
                    mac = device.get("mac", "")
                    if mac:
                        device_map[mac] = device
                # Add history devices
                for device in history:
                    mac = device.get("mac", "")
                    if mac and mac not in device_map:
                        device_map[mac] = device
                # Store merged list
                self.speaker.set_bluetooth_devices(
                    list(device_map.values()), "History loaded"
                )
                self.async_write_ha_state()
        except Exception as err:
            _LOGGER.warning(
                "Failed to load Bluetooth history for %s: %s", self.speaker.name, err
            )

        # Listen for Bluetooth scan completion to auto-update options
        from homeassistant.helpers.dispatcher import async_dispatcher_connect

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"wiim_bluetooth_scan_complete_{self.speaker.uuid}",
                self._handle_scan_complete,
            )
        )

    @callback
    def _handle_scan_complete(self) -> None:
        """Handle Bluetooth scan completion - update entity state."""
        _LOGGER.info(
            "📡 Bluetooth scan complete signal received for %s - refreshing entity state",
            self.speaker.name,
        )
        # Force entity state refresh to update options list
        self.async_write_ha_state()
        # Also schedule a state update to ensure options are refreshed
        self.hass.async_create_task(self._async_refresh_options())

    async def _async_refresh_options(self) -> None:
        """Force refresh of entity options."""
        # Give a moment for the data to settle
        await asyncio.sleep(0.1)
        _LOGGER.info(
            "🔄 Refreshing Bluetooth device select options for %s", self.speaker.name
        )
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return the currently connected Bluetooth device."""
        _LOGGER.debug(
            "Bluetooth select current_option called for %s (BT active: %s, stored MAC: %s)",
            self.speaker.name,
            self.speaker.is_bluetooth_output_active(),
            self._connected_device_mac,
        )
        # Priority 1: If we connected via HA, use stored MAC
        if self._connected_device_mac:
            # Find the device name from history or scan results
            connected_device = self.speaker.get_connected_bluetooth_device()
            if connected_device:
                device_mac = (
                    connected_device.get("mac")
                    or connected_device.get("ad", "").lower()
                )
                if device_mac == self._connected_device_mac.lower():
                    device_name = connected_device.get("name", "Unknown")
                    result = f"{device_name} ({device_mac})"
                    _LOGGER.debug(
                        "Bluetooth select current_option (Priority 1 - HA connected): %s",
                        result,
                    )
                    return result
            # Fallback: just show MAC if we can't find name
            _LOGGER.debug(
                "Bluetooth select current_option (Priority 1 fallback): %s",
                self._connected_device_mac,
            )
            return self._connected_device_mac

        # Priority 2: Get connected device from Bluetooth history (ct=1, role=Audio Sink)
        if self.speaker.is_bluetooth_output_active():
            connected_device = self.speaker.get_connected_bluetooth_device()
            if connected_device:
                device_name = connected_device.get("name", "Unknown")
                device_mac = (
                    connected_device.get("mac")
                    or connected_device.get("ad", "").lower()
                )
                result = f"{device_name} ({device_mac})"
                _LOGGER.debug(
                    "Bluetooth select current_option (Priority 2 - from history): %s",
                    result,
                )
                return result

            # Fallback: try to get from scan results
            devices = self.speaker.get_bluetooth_devices()
            if devices:
                # If we have devices but no connected device from history, show generic
                _LOGGER.debug(
                    "Bluetooth select current_option (Priority 2 fallback): Connected (no device from history)"
                )
                return "Connected"

        _LOGGER.debug(
            "Bluetooth select current_option (default): None (BT output not active or no device)"
        )
        return "None"

    @property
    def options(self) -> list[str]:
        """Return list of available Bluetooth devices from last scan."""
        devices = self.speaker.get_bluetooth_devices()
        options = ["None"]  # Option to disconnect

        _LOGGER.debug(
            "🔍 Bluetooth device select options for %s: %d devices available (scan status: %s)",
            self.speaker.name,
            len(devices),
            self.speaker.get_bluetooth_scan_status(),
        )

        # Add devices from scan/history
        for device in devices:
            name = device.get("name", "Unknown")
            mac = device.get("mac", "")
            if name and mac:
                # Format as "Name (MAC)" for display
                option_str = f"{name} ({mac})"
                options.append(option_str)
                _LOGGER.debug("  Added option: %s", option_str)
            elif mac:
                # If no name, just use MAC
                option_str = f"Unknown Device ({mac})"
                options.append(option_str)
                _LOGGER.debug("  Added option: %s", option_str)
            else:
                _LOGGER.warning("Bluetooth device missing MAC address: %s", device)

        # IMPORTANT: If a device is currently connected (from history), ensure it's in options
        # This is required for Home Assistant to display current_option correctly
        if self.speaker.is_bluetooth_output_active():
            connected_device = self.speaker.get_connected_bluetooth_device()
            _LOGGER.debug(
                "Checking connected device for options: BT active=%s, connected_device=%s",
                self.speaker.is_bluetooth_output_active(),
                connected_device,
            )
            if connected_device:
                device_name = connected_device.get("name", "Unknown")
                device_mac = (
                    connected_device.get("mac")
                    or connected_device.get("ad", "").lower()
                )
                _LOGGER.debug(
                    "Connected device details: name=%s, mac=%s, ad=%s",
                    device_name,
                    device_mac,
                    connected_device.get("ad"),
                )
                if device_name and device_mac:
                    option_str = f"{device_name} ({device_mac})"
                    # Only add if not already in options (avoid duplicates)
                    if option_str not in options:
                        options.append(option_str)
                        _LOGGER.info(
                            "  Added currently connected device to options: %s",
                            option_str,
                        )
                    else:
                        _LOGGER.debug(
                            "  Connected device already in options: %s", option_str
                        )
                else:
                    _LOGGER.debug(
                        "Cannot add connected device to options: name=%s, mac=%s",
                        device_name,
                        device_mac,
                    )
            else:
                _LOGGER.debug(
                    "No connected device found for %s (BT active but no device)",
                    self.speaker.name,
                )

        _LOGGER.debug(
            "✅ Bluetooth device select returning %d options for %s: %s",
            len(options),
            self.speaker.name,
            options,
        )
        return options

    async def async_select_option(self, option: str) -> None:
        """Connect to or disconnect from the selected Bluetooth device."""
        # VERSION MARKER: Updated MAC extraction - 2025-11-04
        _LOGGER.info(
            "WiiM Bluetooth Device Select: User selected '%s' for %s (V2)",
            option,
            self.speaker.name,
        )

        mac_address: str | None = None  # Initialize for error logging context
        try:
            if option == "None":
                # Disconnect
                _LOGGER.info("Disconnecting Bluetooth device for %s", self.speaker.name)
                await self.speaker.coordinator.client.disconnect_bluetooth_device()
                self._connected_device_mac = None
                _LOGGER.info(
                    "Successfully disconnected Bluetooth device for %s",
                    self.speaker.name,
                )
            else:
                # Extract MAC address from option (format: "Name (MAC)")
                # Log the exact option received for debugging
                _LOGGER.debug(
                    "Attempting to extract MAC from option: %r (type: %s, length: %d)",
                    option,
                    type(option).__name__,
                    len(option),
                )

                # Match both uppercase and lowercase hex digits with colon separators
                # Try multiple patterns to handle various formats
                patterns = [
                    # Standard format: "Name (XX:XX:XX:XX:XX:XX)"
                    r"\(([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})\)",
                    # Alternative with dashes: "Name (XX-XX-XX-XX-XX-XX)"
                    r"\(([0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2})\)",
                    # Just the MAC address itself (if option is just the MAC)
                    r"^([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})$",
                ]

                mac_address = None
                for i, pattern in enumerate(patterns):
                    match = re.search(pattern, option)
                    if match:
                        mac_address = match.group(1)
                        # Normalize to colon-separated format
                        mac_address = mac_address.replace("-", ":")
                        _LOGGER.info(
                            "✅ Successfully extracted MAC address: %s from option: %s (pattern %d)",
                            mac_address,
                            option,
                            i + 1,
                        )
                        break
                    else:
                        _LOGGER.debug(
                            "Pattern %d: NO MATCH for option: %s", i + 1, option
                        )

                if not mac_address:
                    # Detailed error logging - CRITICAL for debugging
                    error_details = f"option={option!r}, length={len(option)}, type={type(option).__name__}, repr={option!r}"
                    _LOGGER.error(
                        "❌ FAILED to extract MAC address - %s", error_details
                    )
                    # Show character-by-character breakdown for debugging
                    char_breakdown = " ".join(
                        f"{i}:{ord(c)}" for i, c in enumerate(option[:50])
                    )
                    _LOGGER.error("Character breakdown: %s", char_breakdown)
                    # Raise with detailed message
                    raise ValueError(
                        f"Could not extract MAC address from option: {option} | DEBUG: {error_details}"
                    )
                _LOGGER.info(
                    "Connecting to Bluetooth device %s (%s) for %s",
                    option,
                    mac_address,
                    self.speaker.name,
                )
                _LOGGER.info(
                    "Calling connect_bluetooth_device API for %s (MAC: %s)",
                    self.speaker.name,
                    mac_address,
                )
                try:
                    await self.speaker.coordinator.client.connect_bluetooth_device(
                        mac_address
                    )
                    _LOGGER.info(
                        "connect_bluetooth_device API call completed successfully for %s",
                        mac_address,
                    )
                except Exception as connect_err:
                    _LOGGER.error(
                        "Failed to connect to Bluetooth device %s: %s",
                        mac_address,
                        connect_err,
                        exc_info=True,
                    )
                    raise
                self._connected_device_mac = mac_address
                _LOGGER.info(
                    "Bluetooth connection command sent for %s, verifying pairing status...",
                    mac_address,
                )

                # Verify pairing status after connection (with retries since pairing can take time)
                import asyncio

                pairing_verified = False
                pair_status_result = None
                for attempt in range(6):  # Try for up to 3 seconds (6 attempts × 0.5s)
                    await asyncio.sleep(0.5)  # Give device time to complete pairing
                    try:
                        pair_status = await self.speaker.coordinator.client.get_bluetooth_pair_status()
                        if pair_status and pair_status.get("result", 0) != 0:
                            pairing_verified = True
                            pair_status_result = pair_status.get("result")
                            _LOGGER.info(
                                "Successfully connected and verified pairing for Bluetooth device %s (pairing status: %s)",
                                mac_address,
                                pair_status_result,
                            )
                            break
                    except Exception as pair_err:
                        _LOGGER.debug(
                            "Pairing status check failed (attempt %d/6): %s",
                            attempt + 1,
                            pair_err,
                        )

                if not pairing_verified:
                    _LOGGER.warning(
                        "Bluetooth connection command sent for %s, but pairing status verification timeout or failed. "
                        "Connection may still succeed - check device status.",
                        mac_address,
                    )

                # Refresh coordinator data to get updated Bluetooth status
                _LOGGER.info(
                    "Requesting coordinator refresh after Bluetooth connection for %s",
                    self.speaker.name,
                )
                await self.coordinator.async_request_refresh()

                # Optionally switch output mode to Bluetooth
                try:
                    from .media_controller import MediaPlayerController

                    controller = MediaPlayerController(self.speaker)
                    await controller.select_output_mode("Bluetooth Out")
                    _LOGGER.info(
                        "Switched output mode to Bluetooth for %s", self.speaker.name
                    )
                except Exception as err:
                    _LOGGER.warning(
                        "Failed to switch output mode to Bluetooth (connection may still work): %s",
                        err,
                    )

            # Trigger state update
            self.async_write_ha_state()

        except Exception as err:
            # Enhanced error logging for better debugging
            error_details = []

            # Extract error type
            error_type = type(err).__name__
            error_details.append(f"error_type={error_type}")

            # Check if it's a WiiMRequestError/WiiMConnectionError with additional context
            if hasattr(err, "last_error") and err.last_error:
                underlying_error = err.last_error
                error_details.append(
                    f"underlying_error={type(underlying_error).__name__}: {underlying_error}"
                )

                # Check for HTTP response errors
                if hasattr(underlying_error, "status"):
                    error_details.append(f"http_status={underlying_error.status}")
                if hasattr(underlying_error, "message"):
                    error_details.append(f"http_message={underlying_error.message}")
                if hasattr(underlying_error, "request_info"):
                    error_details.append(
                        f"request_url={underlying_error.request_info.real_url}"
                    )

                # Check for connection errors
                if hasattr(underlying_error, "os_error"):
                    error_details.append(f"os_error={underlying_error.os_error}")

            # Extract endpoint if available
            if hasattr(err, "endpoint") and err.endpoint:
                error_details.append(f"endpoint={err.endpoint}")

            # Extract device info if available
            if hasattr(err, "device_info") and err.device_info:
                device_info = err.device_info
                if device_info.get("firmware_version"):
                    error_details.append(
                        f"firmware={device_info.get('firmware_version')}"
                    )
                if device_info.get("device_model"):
                    error_details.append(f"model={device_info.get('device_model')}")

            # Extract MAC address for context (if available)
            if mac_address:
                error_details.append(f"target_mac={mac_address}")
            elif option and option != "None":
                error_details.append(f"selected_option={option}")

            # Log with all details
            error_msg = (
                f"Failed to connect/disconnect Bluetooth device for {self.speaker.name}"
            )
            if error_details:
                error_msg += f" | {' | '.join(error_details)}"
            else:
                error_msg += f": {err}"

            _LOGGER.error(error_msg, exc_info=True)
            raise

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        devices = self.speaker.get_bluetooth_devices()
        pair_status = self.speaker.get_bluetooth_pair_status()
        is_paired = self.speaker.is_bluetooth_paired()
        bt_output_active = self.speaker.is_bluetooth_output_active()

        # Debug logging to verify pairing status is being read
        _LOGGER.debug(
            "Bluetooth select entity attributes for %s: pair_status=%s, is_paired=%s, bt_output_active=%s",
            self.speaker.name,
            pair_status,
            is_paired,
            bt_output_active,
        )

        attributes = {
            "scan_status": self.speaker.get_bluetooth_scan_status(),
            "devices_found": len(devices),
            "connected_device": self._connected_device_mac,
            "bluetooth_output_active": bt_output_active,
            "bluetooth_paired": is_paired,
        }

        # Add raw pairing status if available
        if pair_status:
            attributes["pairing_status"] = pair_status

        return attributes
