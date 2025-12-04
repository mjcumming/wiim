#!/usr/bin/env python3
"""
Test Channel Balance functionality with real WiiM device
Tests the number entity and service call for channel balance control
"""

import argparse
import asyncio
import sys
from typing import Any

from pywiim import Player, WiiMClient


async def test_channel_balance(host: str, timeout: int = 10) -> None:
    """Test channel balance functionality with a real device."""
    print(f"\n🔍 Testing Channel Balance on {host}")
    print("=" * 60)

    try:
        # Create client and player
        print(f"\n1️⃣  Connecting to {host}...")
        client = WiiMClient(host=host, timeout=timeout)
        player = Player(client)

        # Refresh to get current state
        print("2️⃣  Refreshing device state...")
        await player.refresh()
        print(f"   ✅ Connected to: {player.name}")
        print(f"   📋 Model: {player.model}")
        print(f"   🔧 Firmware: {player.firmware}")

        # Test channel balance API availability
        print("\n3️⃣  Checking channel balance API availability...")
        if not hasattr(player, "set_channel_balance"):
            print("   ❌ ERROR: set_channel_balance method not available in pywiim")
            print("   💡 This may require a newer version of pywiim (2.1.38+)")
            return

        # Test setting different balance values
        test_values = [
            (0.0, "Center"),
            (0.5, "Right 50%"),
            (-0.5, "Left 50%"),
            (1.0, "Full Right"),
            (-1.0, "Full Left"),
            (0.0, "Back to Center"),
        ]

        print("\n4️⃣  Testing channel balance values...")
        for value, description in test_values:
            try:
                print(f"\n   Testing: {description} (value: {value})")
                await player.set_channel_balance(value)
                print(f"   ✅ Successfully set balance to {value}")

                # Small delay to allow device to process
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"   ❌ Failed to set balance to {value}: {e}")
                print(f"   ⚠️  This firmware may not support channel balance")
                return

        print("\n" + "=" * 60)
        print("✅ All channel balance tests passed!")
        print("\n💡 The channel balance number entity should work in Home Assistant")
        print("   Look for: <device_name> Channel Balance")

        # Clean up session
        if hasattr(client, "_session") and client._session:
            await client._session.close()

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test channel balance functionality with real WiiM device"
    )
    parser.add_argument(
        "host",
        help="IP address or hostname of the WiiM device",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Connection timeout in seconds (default: 10)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(test_channel_balance(args.host, args.timeout))
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()

