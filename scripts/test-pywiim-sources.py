#!/usr/bin/env python3
"""
Diagnostic script to inspect what pywiim is returning for input sources.
This helps determine if the issue is in pywiim or our integration code.
"""

import asyncio
import sys
from typing import Any

try:
    from pywiim import Player, WiiMClient
    from pywiim.exceptions import WiiMError
except ImportError:
    print("ERROR: pywiim not installed. Install it with: pip install pywiim")
    sys.exit(1)


async def inspect_pywiim_sources(host: str, port: int = 443) -> None:
    """Inspect what pywiim returns for input sources."""
    print(f"\n{'=' * 80}")
    print(f"Inspecting pywiim source data for {host}:{port}")
    print(f"{'=' * 80}\n")

    try:
        # Create client and player (same as our integration does)
        client = WiiMClient(host=host, port=port, timeout=10)
        player = Player(client)

        # Refresh to get latest data
        print("Refreshing player data...")
        await player.refresh()
        print("✓ Player data refreshed\n")

        # Check device_info
        print("=" * 80)
        print("DEVICE INFO (from player.device_info)")
        print("=" * 80)
        if hasattr(player, "device_info") and player.device_info:
            device_info = player.device_info
            print(f"Device Name: {getattr(device_info, 'name', 'N/A')}")
            print(f"Model: {getattr(device_info, 'model', 'N/A')}")
            print(f"Firmware: {getattr(device_info, 'firmware', 'N/A')}")

            # Check input_list in device_info
            input_list = getattr(device_info, "input_list", None)
            print(f"\ninput_list (from device_info): {input_list}")
            if input_list:
                print(f"  Type: {type(input_list)}")
                print(f"  Length: {len(input_list)}")
                print(f"  Items: {list(input_list)}")
            else:
                print("  ⚠️  input_list is None or missing")
        else:
            print("⚠️  player.device_info is None or missing")

        # Check available_sources
        print("\n" + "=" * 80)
        print("AVAILABLE SOURCES (from player.available_sources)")
        print("=" * 80)
        available_sources = getattr(player, "available_sources", None)
        print(f"available_sources: {available_sources}")
        if available_sources:
            print(f"  Type: {type(available_sources)}")
            if hasattr(available_sources, "__len__"):
                print(f"  Length: {len(available_sources)}")
            if hasattr(available_sources, "__iter__"):
                print(f"  Items: {list(available_sources)}")
        else:
            print("  ⚠️  available_sources is None or missing")

        # Check current source
        print("\n" + "=" * 80)
        print("CURRENT SOURCE")
        print("=" * 80)
        current_source = getattr(player, "source", None)
        print(f"Current source: {current_source}")
        print(f"  Type: {type(current_source)}")

        # Compare the two
        print("\n" + "=" * 80)
        print("COMPARISON")
        print("=" * 80)
        input_list_items = []
        if hasattr(player, "device_info") and player.device_info:
            input_list = getattr(player.device_info, "input_list", None)
            if input_list:
                input_list_items = list(input_list) if hasattr(input_list, "__iter__") else []

        available_sources_items = []
        if available_sources:
            available_sources_items = list(available_sources) if hasattr(available_sources, "__iter__") else []

        print(f"input_list items:        {input_list_items}")
        print(f"available_sources items:  {available_sources_items}")

        if input_list_items and available_sources_items:
            # Find differences
            only_in_input_list = set(input_list_items) - set(available_sources_items)
            only_in_available = set(available_sources_items) - set(input_list_items)
            common = set(input_list_items) & set(available_sources_items)

            print(f"\nCommon sources:          {sorted(common)}")
            if only_in_input_list:
                print(f"Only in input_list:       {sorted(only_in_input_list)}")
            if only_in_available:
                print(f"Only in available_sources: {sorted(only_in_available)}")

            if only_in_input_list or only_in_available:
                print("\n⚠️  WARNING: input_list and available_sources differ!")
                print("   This suggests pywiim may be filtering sources.")
            else:
                print("\n✓ input_list and available_sources match")

        # Check raw API response if possible
        print("\n" + "=" * 80)
        print("RAW API DATA (if accessible)")
        print("=" * 80)
        try:
            # Try to get raw device info
            if hasattr(client, "get_device_info"):
                raw_device_info = await client.get_device_info()
                print(f"Raw device_info response type: {type(raw_device_info)}")
                if isinstance(raw_device_info, dict):
                    if "input_list" in raw_device_info:
                        print(f"Raw input_list from API: {raw_device_info.get('input_list')}")
                    else:
                        print("Available keys in raw device_info:")
                        for key in sorted(raw_device_info.keys()):
                            print(f"  - {key}")
        except Exception as e:
            print(f"Could not access raw API data: {e}")

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print("This diagnostic shows what pywiim is providing to our integration.")
        print("\nIf the source list is wrong:")
        print("  - If input_list/available_sources here is wrong → pywiim issue")
        print("  - If input_list/available_sources here is correct → our integration issue")
        print("\n" + "=" * 80)

    except WiiMError as e:
        print(f"\n❌ WiiM Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python test-pywiim-sources.py <host> [port]")
        print("Example: python test-pywiim-sources.py 192.168.1.100")
        print("Example: python test-pywiim-sources.py 192.168.1.100 443")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 443

    asyncio.run(inspect_pywiim_sources(host, port))


if __name__ == "__main__":
    main()
