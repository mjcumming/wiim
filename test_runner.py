#!/usr/bin/env python3
"""Simple test runner for WiiM integration."""

import asyncio
import sys
from pathlib import Path

# Add the custom_components directory to the path
sys.path.insert(0, str(Path(__file__).parent / "custom_components"))


async def test_basic_import():
    """Test that we can import the basic modules."""
    try:
        from wiim.api import WiiMClient
        from wiim.const import DOMAIN

        print("✅ Basic imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


async def test_client_creation():
    """Test that we can create a client."""
    try:
        from wiim.api import WiiMClient

        client = WiiMClient("192.168.1.100")
        print("✅ Client creation successful")
        return True
    except Exception as e:
        print(f"❌ Client creation failed: {e}")
        return False


async def main():
    """Run basic tests."""
    print("🧪 Running basic WiiM integration tests...")

    tests = [
        test_basic_import,
        test_client_creation,
    ]

    results = []
    for test in tests:
        result = await test()
        results.append(result)

    passed = sum(results)
    total = len(results)

    print(f"\n📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All basic tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
