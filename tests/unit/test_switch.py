"""Unit tests for WiiM switch platform."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSwitchConstants:
    """Test switch platform constants."""

    async def test_eq_preset_map(self):
        """Test EQ preset map constant."""
        from custom_components.wiim.const import EQ_PRESET_MAP

        assert isinstance(EQ_PRESET_MAP, dict)
        assert len(EQ_PRESET_MAP) > 10  # Should have multiple presets

        # Test specific presets exist
        assert "flat" in EQ_PRESET_MAP
        assert "rock" in EQ_PRESET_MAP
        assert "jazz" in EQ_PRESET_MAP
        assert "pop" in EQ_PRESET_MAP

        # Test preset values are strings
        for key, value in EQ_PRESET_MAP.items():
            assert isinstance(value, str)
            assert len(value) > 0

    def test_conf_enable_eq_controls(self):
        """Test EQ controls configuration constant."""
        from custom_components.wiim.switch import CONF_ENABLE_EQ_CONTROLS

        assert CONF_ENABLE_EQ_CONTROLS == "enable_eq_controls"


class TestSwitchPlatformSetup:
    """Test switch platform setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_eq_enabled(self):
        """Test switch platform setup when EQ controls are enabled."""
        from custom_components.wiim.switch import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker lookup
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.switch.get_speaker_from_config_entry", return_value=speaker):
            # Mock entry data
            hass.data = {"wiim": {"test-entry": {"entry": MagicMock(options={"enable_eq_controls": True})}}}

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create equalizer switch
            assert len(entities) == 1
            assert entities[0].__class__.__name__ == "WiiMEqualizerSwitch"

    @pytest.mark.asyncio
    async def test_async_setup_entry_eq_disabled(self):
        """Test switch platform setup when EQ controls are disabled."""
        from custom_components.wiim.switch import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker lookup
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.switch.get_speaker_from_config_entry", return_value=speaker):
            # Mock entry data without EQ controls enabled
            hass.data = {"wiim": {"test-entry": {"entry": MagicMock(options={"enable_eq_controls": False})}}}

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create no switches
            assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_async_setup_entry_no_options(self):
        """Test switch platform setup with no options configured."""
        from custom_components.wiim.switch import async_setup_entry

        # Mock dependencies
        hass = MagicMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry"

        # Mock speaker lookup
        speaker = MagicMock()
        speaker.name = "Test WiiM"

        with patch("custom_components.wiim.switch.get_speaker_from_config_entry", return_value=speaker):
            # Mock entry data with no options
            hass.data = {"wiim": {"test-entry": {"entry": MagicMock(options={})}}}

            entities = []
            async_add_entities = MagicMock()

            await async_setup_entry(hass, config_entry, async_add_entities)

            # Verify entities were created
            async_add_entities.assert_called_once()
            entities = async_add_entities.call_args[0][0]

            # Should create no switches
            assert len(entities) == 0
