# Development Documentation

Technical documentation for WiiM integration developers and contributors.

## 🚀 **Quick Start - Running Home Assistant**

To start Home Assistant with the WiiM integration for development:

```bash
# 1. Run quick checks first (catches syntax/lint errors before starting HA)
make pre-run

# 2. From any directory, start HA with explicit config path
hass -c /workspaces/core/config --open-ui
```

**Important**:

- Always use the `-c /workspaces/core/config` flag to ensure HA loads the correct configuration directory with the symlinked WiiM integration.
- Run `make pre-run` before starting HA to catch syntax errors, linting issues, and import problems early.

## 🏗️ **Architecture Overview**

This integration is a **thin glue layer** between the `pywiim` library and Home Assistant.

### What pywiim Handles

- ✅ Device communication (HTTP API)
- ✅ Discovery (SSDP/UPnP)
- ✅ Polling strategy
- ✅ State management
- ✅ Data parsing
- ✅ Business logic
- ✅ UPnP subscriptions

### What the Integration Does

- ✅ Creates HA entities
- ✅ Reads from pywiim client/coordinator
- ✅ Calls pywiim methods for control
- ✅ HA-specific setup (config flow, device registry)

### Key Principle

**If it's not directly gluing pywiim to HA, it shouldn't be here.**

For detailed API documentation, polling strategies, and UPnP architecture, see the [pywiim library documentation](https://github.com/mjcumming/pywiim).

## 📋 **Essential Technical Docs**

| Document                                                               | Purpose                          | Audience   |
| ---------------------------------------------------------------------- | -------------------------------- | ---------- |
| **[../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)**                 | Complete architecture guide      | Developers |
| **[../docs/DEVELOPMENT-RULES.md](../docs/DEVELOPMENT-RULES.md)**       | Development rules and guidelines | Developers |
| **[../docs/TESTING-CONSOLIDATED.md](../docs/TESTING-CONSOLIDATED.md)** | Testing strategy                 | Developers |

## 🎯 **For New Contributors**

1. **[../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - ⭐ START HERE - Complete architecture guide
2. **[../docs/DEVELOPMENT-RULES.md](../docs/DEVELOPMENT-RULES.md)** - Development rules and guidelines
3. **[../CONTRIBUTING.md](../CONTRIBUTING.md)** - Contribution workflow
4. **[../docs/TESTING-CONSOLIDATED.md](../docs/TESTING-CONSOLIDATED.md)** - Testing strategy

## 📚 **External References**

- **[Home Assistant Developer Docs](https://developers.home-assistant.io/)** - HA development guidelines
- **[pywiim Library](https://github.com/mjcumming/pywiim)** - Core library handling all device communication
- **[Arylic LinkPlay API](https://developer.arylic.com/httpapi/)** - Official API documentation (reference only)

## 🔍 **Code Structure**

The integration follows a simple pattern:

```
custom_components/wiim/
├── __init__.py          # Setup entry, create pywiim client/coordinator
├── config_flow.py       # Use pywiim discovery, create config entry
├── coordinator.py       # Thin wrapper around pywiim
├── data.py              # Minimal Speaker wrapper (holds coordinator)
├── entity.py            # Base entity class
├── media_player.py      # Media player entity (reads coordinator, calls pywiim)
├── sensor.py            # Sensor entities (read from coordinator)
├── select.py            # Select entities (read coordinator, call pywiim)
├── switch.py            # Switch entities (read coordinator, call pywiim)
├── number.py            # Number entities (read coordinator, call pywiim)
├── button.py            # Button entities (call pywiim)
└── const.py             # HA constants only
```

All entities read from `coordinator.data` (from pywiim) and call `coordinator.client.method()` for control.

---

**For user documentation, see [../docs/README.md](../docs/README.md)**
