# Docker Networking for UPnP Development

## Overview

This document explains the critical networking requirements for developing the WiiM integration, particularly when working with UPnP event subscriptions in a Docker container environment.

## The Problem

The WiiM integration uses **UPnP** for real-time event notifications from speakers. UPnP relies on SSDP (Simple Service Discovery Protocol), which uses multicast UDP packets to communicate with devices on the local network.

**Default Docker bridge networking blocks multicast traffic**, which means UPnP subscriptions fail in a standard devcontainer environment.

## Dev/Prod Parity Requirement

Home Assistant production instances typically run with `network_mode: host` to ensure UPnP and other discovery protocols work correctly. To avoid "it works on my machine" syndrome, **development must mirror production** by using host networking.

## Solution: Configure Host Networking

### For VS Code DevContainers

Edit `.devcontainer/devcontainer.json` and add `--network=host` to the `runArgs`:

```json
{
  "runArgs": [
    "-e",
    "GIT_EDITOR=code --wait",
    "--security-opt",
    "label=disable",
    "--network=host" // Add this line
  ]
}
```

**Important**: After making this change, rebuild your devcontainer:

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Select "Dev Containers: Rebuild Container"

### For Docker Compose

If using `docker-compose.yml` directly:

```yaml
version: "3"
services:
  homeassistant-dev:
    image: ghcr.io/home-assistant/home-assistant:stable
    network_mode: host # Use host networking
    volumes:
      - ./config:/config
      - ./custom_components:/config/custom_components
```

## What This Changes

### Before (Bridge Mode)

- Container gets isolated IP: `192.168.65.3` (WSL NAT network)
- Devices on `192.168.1.x` cannot reach container
- UPnP subscriptions fail silently
- System falls back to HTTP polling

### After (Host Mode)

- Container shares host's network stack
- Devices can send UPnP events to container
- UPnP subscriptions work as designed
- Real-time updates without excessive polling

## Technical Details

### Why Bridge Mode Fails

UPnP/SSDP sends UDP multicast packets to `239.255.255.250:1900`. Bridge networks:

1. **Isolate multicast traffic** - Only reachable within the virtual bridge
2. **Use NAT** - Traffic must be explicitly mapped with `-p` flag
3. **Can't map multicast** - Multicast protocols don't work with port mapping

### Why Host Mode Works

Host mode eliminates the network isolation:

1. **Direct network access** - Container uses host's IP addresses
2. **No NAT overhead** - Reduced latency for network calls
3. **Multicast support** - Can receive broadcast/multicast packets natively

### Security Considerations

Host networking reduces container isolation:

- ✅ **Acceptable for local development** - Firewalled local network
- ❌ **Not recommended for production internet-facing servers** - If you need strong isolation

For Home Assistant development on a local network, this is standard practice.

## Verification

After configuring host networking, start Home Assistant and check the logs:

**✅ Success (Host Network):**

```
Detected local IP for UPnP callback: 192.168.1.123  # Your LAN IP
Successfully subscribed to UPnP services for 192.168.1.68
✅ UPnP event subscriptions started successfully
```

**❌ Failure (Bridge Network):**

```
⚠️  Detected container/WSL IP 192.168.65.3 - devices on your LAN may not be able to reach this
```

## Fallback Behavior

The integration is designed to gracefully handle UPnP failures:

- **Default**: UPnP disabled (relies on HTTP polling)
- **Interval**: 1 second when playing, 5 seconds when idle
- **Status**: Visible in diagnostics under `upnp_status`

This ensures the integration works even without host networking, but at the cost of higher API usage.

## References

- [Home Assistant Container Networking](https://www.home-assistant.io/installation/linux#networking)
- [Docker Network Modes](https://docs.docker.com/network/drivers/)
- [UPnP Discovery Protocol](https://openconnectivity.org/specs/OCF_UPnP_Discovery_Specification_v1.1.pdf)

## Code References

- `upnp_client.py` - Handles network IP detection and warnings
- `data.py` - UPnP initialization with Docker networking notes
- `.devcontainer/devcontainer.json` - Development container configuration
