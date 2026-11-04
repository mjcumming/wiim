"""Tests for the integration's Home Assistant configuration schema."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.wiim.const import DOMAIN


@pytest.mark.asyncio
async def test_yaml_setup_creates_repair_issue(hass: HomeAssistant) -> None:
    """Unsupported YAML is reported while integration setup remains available."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"host": "192.0.2.1"}})

    issue = ir.async_get(hass).async_get_issue("homeassistant", f"config_entry_only_{DOMAIN}")
    assert issue is not None
    assert issue.issue_domain == DOMAIN
