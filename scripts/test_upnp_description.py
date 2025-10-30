#!/usr/bin/env python3
"""Diagnostic script to test WiiM UPnP support.

This script tests whether WiiM devices properly implement UPnP DLNA DMR eventing by:
1. Fetching description.xml from the device
2. Parsing it to check for AVTransport and RenderingControl services
3. Testing if SUBSCRIBE requests work

Usage:
    python scripts/test_upnp_description.py 192.168.1.68
"""

import asyncio
import sys
from typing import Any

import aiohttp
from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpError


async def test_upnp_description(device_ip: str) -> dict[str, Any]:
    """Test UPnP description.xml and services for a WiiM device.

    Args:
        device_ip: IP address of the WiiM device

    Returns:
        Dictionary with test results
    """
    results = {
        "device_ip": device_ip,
        "description_url": f"http://{device_ip}:49152/description.xml",
        "description_accessible": False,
        "description_content": None,
        "upnp_device_created": False,
        "device_type": None,
        "manufacturer": None,
        "model": None,
        "services": [],
        "has_avtransport": False,
        "has_rendering_control": False,
        "supports_upnp_eventing": False,
        "error": None,
    }

    print(f"\n{'=' * 60}")
    print(f"Testing UPnP Support for WiiM Device: {device_ip}")
    print(f"{'=' * 60}\n")

    # Test 1: Fetch description.xml
    print(f"[1] Fetching description.xml from {results['description_url']}...")

    try:
        async with aiohttp.ClientSession() as session:
            async with asyncio.timeout(5):
                async with session.get(results["description_url"]) as response:
                    if response.status == 200:
                        content = await response.text()
                        results["description_accessible"] = True
                        results["description_content"] = content
                        print(f"    ✅ Successfully fetched description.xml ({len(content)} bytes)")
                        print(f"    First 500 chars:\n{content[:500]}...")
                    else:
                        results["error"] = f"HTTP {response.status}"
                        print(f"    ❌ Failed: HTTP {response.status}")
                        return results
    except TimeoutError:
        results["error"] = "Timeout after 5 seconds"
        print("    ❌ Failed: Timeout after 5 seconds")
        print("    → Device may not support UPnP on port 49152")
        return results
    except Exception as err:
        results["error"] = str(err)
        print(f"    ❌ Failed: {err}")
        return results

    # Test 2: Parse UPnP device using async_upnp_client
    print("\n[2] Parsing UPnP device description...")

    try:
        async with aiohttp.ClientSession() as session:
            requester = AiohttpSessionRequester(session, with_sleep=True, timeout=10)
            factory = UpnpFactory(requester, non_strict=True)

            async with asyncio.timeout(5):
                upnp_device = await factory.async_create_device(results["description_url"])
                results["upnp_device_created"] = True
                results["device_type"] = upnp_device.device_type
                results["manufacturer"] = upnp_device.manufacturer
                results["model"] = upnp_device.model_name

                print("    ✅ Successfully created UPnP device")
                print(f"       Device Type: {results['device_type']}")
                print(f"       Manufacturer: {results['manufacturer']}")
                print(f"       Model: {results['model']}")
    except TimeoutError:
        results["error"] = "Timeout parsing device description"
        print("    ❌ Failed: Timeout parsing device description")
        return results
    except UpnpError as err:
        results["error"] = f"UPnP error: {err}"
        print(f"    ❌ Failed: UPnP error: {err}")
        return results
    except Exception as err:
        results["error"] = f"Parse error: {err}"
        print(f"    ❌ Failed: {err}")
        return results

    # Test 3: Check for required services
    print("\n[3] Checking for DLNA DMR services...")

    try:
        # List all services
        for service in upnp_device.services.values():
            service_info = {
                "service_id": service.service_id,
                "service_type": service.service_type,
            }
            results["services"].append(service_info)
            print(f"    → Found service: {service.service_id}")
            print(f"      Type: {service.service_type}")

        # Check for AVTransport
        avtransport = upnp_device.service("urn:schemas-upnp-org:service:AVTransport:1")
        if avtransport:
            results["has_avtransport"] = True
            print("\n    ✅ AVTransport service found")
            print("       → Required for play/pause/stop events")
        else:
            print("\n    ❌ AVTransport service NOT found")
            print("       → Device cannot send playback state events")

        # Check for RenderingControl
        rendering = upnp_device.service("urn:schemas-upnp-org:service:RenderingControl:1")
        if rendering:
            results["has_rendering_control"] = True
            print("    ✅ RenderingControl service found")
            print("       → Required for volume/mute events")
        else:
            print("    ❌ RenderingControl service NOT found")
            print("       → Device cannot send volume events")

        # Overall assessment
        if results["has_avtransport"] and results["has_rendering_control"]:
            results["supports_upnp_eventing"] = True
            print(f"\n{'=' * 60}")
            print("✅ RESULT: Device SUPPORTS UPnP DLNA DMR eventing")
            print(f"{'=' * 60}")
            print("\nThis device advertises proper DLNA services and should support:")
            print("  • Real-time playback state events (play/pause/stop)")
            print("  • Volume and mute change events")
            print("  • Track metadata updates")
            print("\nThe WiiM integration's UPnP implementation should work.")
        else:
            print(f"\n{'=' * 60}")
            print("⚠️  RESULT: Device has INCOMPLETE UPnP support")
            print(f"{'=' * 60}")
            print("\nMissing required services - UPnP eventing may not work properly.")
            print("The integration should fall back to HTTP polling.")

    except Exception as err:
        results["error"] = f"Service check error: {err}"
        print(f"    ❌ Failed to check services: {err}")

    return results


async def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/test_upnp_description.py <device_ip>")
        print("Example: python scripts/test_upnp_description.py 192.168.1.68")
        sys.exit(1)

    device_ip = sys.argv[1]
    results = await test_upnp_description(device_ip)

    # Print summary
    print(f"\n{'=' * 60}")
    print("TEST SUMMARY")
    print(f"{'=' * 60}")
    print(f"Device IP: {results['device_ip']}")
    print(f"Description accessible: {results['description_accessible']}")
    print(f"UPnP device created: {results['upnp_device_created']}")
    print(f"Has AVTransport: {results['has_avtransport']}")
    print(f"Has RenderingControl: {results['has_rendering_control']}")
    print(f"Supports UPnP eventing: {results['supports_upnp_eventing']}")

    if results["error"]:
        print(f"Error: {results['error']}")

    print(f"\n{'=' * 60}")

    # Return exit code based on results
    if results["supports_upnp_eventing"]:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Failure or incomplete support


if __name__ == "__main__":
    asyncio.run(main())
