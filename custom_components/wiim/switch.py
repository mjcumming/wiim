"""Switch platform for WiiM."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WiiMEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up switch entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([WiiMBinarySwitch(coordinator, entry)])


class WiiMBinarySwitch(WiiMEntity, SwitchEntity):
    """wiim switch class."""

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        """Turn on the switch."""
        await self.coordinator.api.async_set_title("bar")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """Turn off the switch."""
        await self.coordinator.api.async_set_title("foo")
        await self.coordinator.async_request_refresh()

    @property
    def name(self):
        """Return the name of the switch."""
        return "WiiM_Switch"

    @property
    def icon(self):
        """Return the icon of this switch."""
        return "mdi:toggle-switch"

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self.coordinator.data.get("title", "") == "foo"
