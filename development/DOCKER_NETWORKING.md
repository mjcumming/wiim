# Docker Networking for łiiM Integration Development

## Overview

The łiiM integration uses UPnP for real-time event notifications from devices. This requires specific Docker networking configuration for proper operation.

## The UPnP Networking Requirement

UPnP uses SSDP (Simple Service Discovery Protocol) which relies on UDP multicast packets. These packets must be able to travel between the container and the physical network to allow:

- Device discovery
- Event subscription callbacks

## Native Linux / macOS Docker Desktop

For native Linux or macOS Docker Desktop, use host networking mode as documented in the architectural guide.

### Devcontainer Configuration

Add to `.devcontainer/devcontainer.json`:

```json
{
  "runArgs": ["--network=host"]
}
```

This allows the container to:

- Bind directly to host network interfaces
- Send/receive multicast packets
- Be reachable by devices on your LAN

## WSL2 Limitation

**Important**: When developing on Windows using WSL2, UPnP will NOT work even with `--network=host` specified.

### Why WSL2 UPnP Fails

WSL2 creates its own virtualized network stack:

- The container sees WSL2's network (`192.168.65.x`) not Windows LAN IP
- Devices on your physical network cannot reach WSL2 container IPs
- UPnP event callbacks from devices fail

### Example in Logs

```
2025-10-28 20:49:01.566 WARNING [custom_components.wiim.upnp_client]
⚠️  Detected container/WSL IP 192.168.65.3 - devices on your LAN may not be able to reach this for UPnP events
```

### What Happens

1. UPnP code initializes correctly ✅
2. Subscriptions are attempted ✅
3. Callback URL is unreachable from device network ❌
4. Integration gracefully falls back to HTTP polling ✅

**Result**: Integration works using HTTP polling (no UPnP events) on WSL2

## Solutions for WSL2

### Option 1: Accept HTTP Polling Fallback (Recommended for WSL2)

The integration will work perfectly using HTTP polling. You lose real-time events but functionality is maintained. This is sufficient for development.

### Option 2: Use Native Linux or WSL1

- Native Linux: UPnP works with host networking
- WSL1: Uses Windows networking directly (may work with port mapping)

### Option 3: Use Docker Desktop for Windows (Hyper-V)

Docker Desktop on Windows uses Hyper-V virtualization which may support proper network bridging (requires testing).

### Option 4: Remote Linux Development

Develop on a remote Linux server or VM with host networking enabled.

## Production Deployment

In production, the integration will work correctly with UPnP when running on native Linux with host networking or in a properly configured Kubernetes/Docker environment.

## Verification

To check if UPnP is working:

1. Check logs for subscription success:

   ```
   ✅ UPnP event subscriptions started successfully
   ```

2. Check diagnostics for UPnP status:
   Settings → Devices & Services → łiiM → Diagnostics
   Look for: `"upnp": { "status": "Active" }`

3. Watch for real-time event notifications (vs polling)

## References

- [Docker Network Drivers](https://docs.docker.com/network/drivers/)
- [WSL2 Networking](https://learn.microsoft.com/en-us/windows/wsl/networking)
- UPnP Specification: [SOAP-over-UDP](http://upnp.org/specs/arch/UPnP-arch-DeviceArchitecture-v2.0.pdf)
