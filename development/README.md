# Development Documentation

> **Purpose**: Technical documentation for WiiM integration developers and contributors.

---

## 📋 **Development Documentation Index**

### **🏗️ Architecture & Design**

| Document                                     | Purpose                                                               | Audience                |
| -------------------------------------------- | --------------------------------------------------------------------- | ----------------------- |
| **[ARCHITECTURE.md](ARCHITECTURE.md)**       | Complete architecture design, patterns, and design decisions          | Developers/Contributors |
| **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** | Complete development guide: coding standards, testing, workflow       | Developers/Contributors |
| **[API_GUIDE.md](API_GUIDE.md)**             | API compatibility, group management, defensive programming strategies | API Developers          |

### **🤝 Contributing**

| Document                               | Purpose                              | Audience     |
| -------------------------------------- | ------------------------------------ | ------------ |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Contribution guidelines and workflow | Contributors |
| **[TODO.md](TODO.md)**                 | Development status and roadmap       | Contributors |

---

## 🎯 **Quick Start for Developers**

### **New Contributors**

1. **[CONTRIBUTING.md](CONTRIBUTING.md)** - Start here for contribution workflow
2. **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Development standards and patterns
3. **[TODO.md](TODO.md)** - Current development status and priorities

### **Architecture Understanding**

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Speaker-centric design principles
2. **[API_GUIDE.md](API_GUIDE.md)** - WiiM/LinkPlay API integration patterns

---

## 📚 **External References**

- **[Home Assistant Developer Docs](https://developers.home-assistant.io/)** - HA development guidelines
- **[Arylic LinkPlay API](https://developer.arylic.com/httpapi/)** - Official API documentation
- **[Sonos Integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/sonos)** - Reference architecture patterns

---

## 📝 **Documentation Reorganization**

This `development/` directory was created to separate technical documentation from user guides:

### **What Moved Here** ✅

- **ARCHITECTURE.md** - Technical architecture design (from root)
- **DEVELOPER_GUIDE.md** - Development standards (from docs/)
- **API_GUIDE.md** - API integration patterns (from root, consolidated duplicate from docs/)
- **CONTRIBUTING.md** - Contribution workflow (from root)
- **TODO.md** - Development roadmap (from root)

### **What Stays in `/docs/`** 📚

- **User-focused documentation** - Installation, configuration, features, troubleshooting
- **End-user guides** - Multiroom setup, automation examples
- **Entity references** - What users see in their HA instance

### **Benefits of Reorganization** 🎯

- **Clear Separation** - Developer vs user concerns
- **Reduced Duplication** - Single source of truth for API documentation
- **Easier Navigation** - Users find user docs, developers find dev docs
- **Cleaner Project** - Logical file organization

**For user documentation, see [../docs/README.md](../docs/README.md)**
