#!/usr/bin/env python3
"""Resolve TTS URL and test fetch - run from terminal to verify URLs."""

import asyncio
import json
import os
import sys

# Add HA to path
sys.path.insert(0, "/workspaces/core")
os.chdir("/workspaces/core")

from homeassistant.components import media_source
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url
from homeassistant.helpers.typing import ConfigType
import homeassistant.bootstrap as bootstrap


async def main():
    # Minimal bootstrap to resolve media
    hass = HomeAssistant()
    hass.config.config_dir = "/workspaces/core/config"
    await bootstrap.async_setup_component(hass, "homeassistant", {})
    await bootstrap.async_setup_component(hass, "http", {})
    await bootstrap.async_setup_component(hass, "tts", {})
    await bootstrap.async_setup_component(hass, "media_source", {})
    await bootstrap.async_setup_component(hass, "google_translate", {})

    media_id = "media-source://tts/tts.google_translate_en_com?message=UrlTest&cache=false"
    print(f"Resolving: {media_id}")
    try:
        item = media_source.async_parse_identifier(hass, media_id)
        media = await media_source.async_resolve_media(hass, media_id, None)
        url = media.url
        print(f"Resolved URL: {url}")

        # Process for device (adds base if relative, signs if needed)
        from homeassistant.components.media_player.browse_media import async_process_play_media_url

        play_url = async_process_play_media_url(hass, url)
        print(f"Play URL (after process): {play_url}")

        # Test fetch
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(play_url) as resp:
                print(f"Fetch test: HTTP {resp.status}, size {resp.content_length or 0}")
                body = await resp.read()
                print(f"Actual bytes: {len(body)}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await hass.async_stop()


if __name__ == "__main__":
    asyncio.run(main())
