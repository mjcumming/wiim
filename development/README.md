# Development Documentation

Technical documentation for WiiM integration developers and contributors.

## 🚀 **Quick Start - Running Home Assistant**

To start Home Assistant with the WiiM integration for development:

```bash
# From any directory, start HA with explicit config path
hass -c /workspaces/core/config --open-ui
```

**Important**: Always use the `-c /workspaces/core/config` flag to ensure HA loads the correct configuration directory with the symlinked WiiM integration.

## 📋 **Essential Technical Docs**

| Document                                         | Purpose                                               | Audience       |
| ------------------------------------------------ | ----------------------------------------------------- | -------------- |
| **[API_GUIDE.md](API_GUIDE.md)**                 | WiiM/LinkPlay API reference and defensive programming | API Developers |
| **[ARCHITECTURE.md](ARCHITECTURE.md)**           | Integration design patterns and decisions             | Developers     |
| **[UPNP_ARCHITECTURE.md](UPNP_ARCHITECTURE.md)** | UPnP event architecture and hybrid approach           | Developers     |
| **[UPNP_TESTING.md](UPNP_TESTING.md)**           | UPnP testing and troubleshooting                      | Developers     |
| **[DOCKER_NETWORKING.md](DOCKER_NETWORKING.md)** | Docker networking for UPnP development                | Developers     |

## 🎯 **For New Contributors**

1. **[CONTRIBUTING.md](CONTRIBUTING.md)** - Start here for contribution workflow
2. **[DOCKER_NETWORKING.md](DOCKER_NETWORKING.md)** - **IMPORTANT**: Set up host networking for UPnP
3. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Understand design patterns and decisions
4. **[API_GUIDE.md](API_GUIDE.md)** - Learn API integration patterns

## 📚 **External References**

- **[Home Assistant Developer Docs](https://developers.home-assistant.io/)** - HA development guidelines
- **[Arylic LinkPlay API](https://developer.arylic.com/httpapi/)** - Official API documentation

---

**For user documentation, see [../docs/README.md](../docs/README.md)**
