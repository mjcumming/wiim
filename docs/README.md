# WiiM Integration - User Documentation

> **Purpose**: Complete user guide for the WiiM Home Assistant integration.

---

## 📚 **User Documentation**

### **🚀 Getting Started**

| Document                                 | Purpose                          | When to Use                 |
| ---------------------------------------- | -------------------------------- | --------------------------- |
| **[installation.md](installation.md)**   | Installation via HACS or manual  | First-time setup            |
| **[configuration.md](configuration.md)** | Device configuration and options | Customizing device behavior |
| **[features.md](features.md)**           | Complete feature overview        | Understanding capabilities  |

### **🎵 Advanced Features**

| Document                           | Purpose                               | When to Use                   |
| ---------------------------------- | ------------------------------------- | ----------------------------- |
| **[multiroom.md](multiroom.md)**   | Multiroom audio setup and management  | Setting up speaker groups     |
| **[automation.md](automation.md)** | Automation scripts and examples       | Creating smart audio scenes   |
| **[ENTITIES.md](ENTITIES.md)**     | Entity reference and role sensor info | Understanding entity behavior |

### **🔧 Support**

| Document                                     | Purpose                     | When to Use          |
| -------------------------------------------- | --------------------------- | -------------------- |
| **[troubleshooting.md](troubleshooting.md)** | Common issues and solutions | When things go wrong |

---

## 🎯 **Quick Start Path**

### **New Users**

1. **[installation.md](installation.md)** - Install the integration
2. **[configuration.md](configuration.md)** - Configure your devices
3. **[features.md](features.md)** - Explore what you can do
4. **[multiroom.md](multiroom.md)** - Set up speaker groups (optional)

### **Automation Enthusiasts**

1. **[ENTITIES.md](ENTITIES.md)** - Understand available entities
2. **[automation.md](automation.md)** - Copy/paste automation examples
3. **[multiroom.md](multiroom.md)** - Advanced group management

### **Having Issues?**

1. **[troubleshooting.md](troubleshooting.md)** - Common solutions
2. **[GitHub Issues](https://github.com/mjcumming/wiim/issues)** - Report bugs
3. **[HA Community](https://community.home-assistant.io/)** - Get help

---

## 🎊 **Key Features Highlights**

### **🔑 Essential Entities (Always Available)**

- **Media Player** - Full device control (play, pause, volume, grouping)
- **🔴 Multiroom Role Sensor** - **CRITICAL** for understanding group status
  - States: `Solo`, `Master`, `Slave`
  - **Always visible** - never hidden in diagnostics
  - Essential for troubleshooting and automation

### **🎵 Smart Source Detection**

Shows what you actually care about:

- **"Amazon Music"** instead of "WiFi"
- **"Spotify"** instead of "Network"
- **"AirPlay"** instead of "Mode 99"

### **🎛️ Multiroom Excellence**

- **Native HA Grouping** - Built-in group button support
- **Group Entities** - Optional virtual group controllers
- **Synchronized Control** - Perfect audio sync across speakers
- **Stable Operations** - Dramatically improved reliability

---

## 📋 **Integration Status**

**✅ Production Ready** - World-class quality achieved:

- ✅ **Essential-Only Entities** - Clean UI
- ✅ **Always-Visible Role Sensor** - Critical multiroom understanding
- ✅ **Sonos-Inspired Architecture** - Battle-tested patterns
- ✅ **Universal Compatibility** - Works across entire LinkPlay ecosystem
- ✅ **Defensive Programming** - Graceful API fallbacks

---

**For developer documentation, see [../development/README.md](../development/README.md)**
