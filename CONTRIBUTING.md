# Contributing to WiiM Audio Integration

Thank you for your interest in contributing to the WiiM Audio integration for Home Assistant! This guide will help you get started with development and ensure your contributions align with the project's standards.

## 📋 Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Documentation](#documentation)
- [Community](#community)

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**: Required for Home Assistant 2024.12+
- **Home Assistant Development Environment**: For testing integration
- **Git**: For version control
- **Code Editor**: VS Code recommended with Python extensions

### Skills Helpful

- **Python**: Async/await, type hints, object-oriented programming
- **Home Assistant**: Integration patterns, entity platform development
- **Network Protocols**: HTTP APIs, UPnP/SSDP, mDNS/Zeroconf
- **Audio Systems**: Understanding of multiroom audio concepts

---

## 🔧 Development Setup

### 1. Fork and Clone Repository

```bash
# Fork repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/wiim.git
cd wiim

# Add upstream remote
git remote add upstream https://github.com/mjcumming/wiim.git
```

### 2. Home Assistant Development Environment

#### Option A: Home Assistant Container Development

```bash
# Use Home Assistant development container
git clone https://github.com/home-assistant/core.git
cd core
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Copy integration to development config
mkdir -p config/custom_components
ln -s /path/to/wiim/custom_components/wiim config/custom_components/
```

#### Option B: Production Home Assistant Testing

```bash
# Copy to existing Home Assistant installation
cp -r custom_components/wiim /config/custom_components/

# Restart Home Assistant
# Test integration functionality
```

### 3. Install Development Dependencies

```bash
# Code formatting and linting
pip install black ruff pre-commit

# Testing
pip install pytest pytest-asyncio pytest-homeassistant-custom-component

# Documentation
pip install mkdocs mkdocs-material
```

### 4. Set Up Pre-commit Hooks

```bash
pre-commit install
```

---

## 📝 Code Standards

### Code Style

- **Formatting**: Use `black` with 120 character line length
- **Linting**: Use `ruff` for code quality checks
- **Type Hints**: Required for all function signatures
- **Docstrings**: Google-style docstrings for all public functions

```python
async def example_function(device_ip: str, timeout: float = 10.0) -> dict[str, Any]:
    """Example function with proper typing and docstring.

    Args:
        device_ip: IP address of the WiiM device.
        timeout: Request timeout in seconds.

    Returns:
        Dictionary containing device status information.

    Raises:
        WiiMError: If device communication fails.
    """
```

### File Organization

```
custom_components/wiim/
├── __init__.py          # Integration setup and platform loading
├── manifest.json        # Integration metadata
├── const.py            # Constants and configuration
├── api.py              # WiiM HTTP API client
├── coordinator.py      # Data update coordinator
├── media_player.py     # Media player entity implementation
├── group_media_player.py # Group entity implementation
├── config_flow.py      # Setup wizard and options
├── strings.json        # UI text and translations
└── services.yaml       # Service definitions
```

### Architecture Principles

1. **Separation of Concerns**: API client, coordinator, and entities have distinct responsibilities
2. **Async First**: All I/O operations must be asynchronous
3. **Error Handling**: Graceful degradation and user-friendly error messages
4. **Resource Management**: Proper cleanup of connections and sessions
5. **State Consistency**: Maintain accurate device state across all entities

---

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_api.py

# Run with coverage
pytest --cov=custom_components.wiim
```

### Integration Testing

```bash
# Test with real devices (requires WiiM speakers on network)
pytest tests/test_integration.py --device-ip 192.168.1.100

# Mock testing (no real devices required)
pytest tests/test_mock.py
```

### Manual Testing Checklist

- [ ] Device discovery (UPnP, Zeroconf, manual)
- [ ] Basic playback controls (play, pause, volume)
- [ ] Multiroom group creation and management
- [ ] Group entity functionality
- [ ] Config flow and options flow
- [ ] Error handling (network disconnection, device offline)
- [ ] Home Assistant restart resilience

---

## 📤 Submitting Changes

### Workflow

1. **Create Feature Branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**

   - Follow code standards
   - Add tests for new functionality
   - Update documentation

3. **Commit Changes**

   ```bash
   # Use conventional commit format
   git commit -m "feat: add multiroom volume synchronization"
   git commit -m "fix: handle session timeout during playback"
   git commit -m "docs: update multiroom setup guide"
   ```

4. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   # Create pull request on GitHub
   ```

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Build process or auxiliary tool changes

### Pull Request Guidelines

- **Title**: Clear, descriptive title
- **Description**: Explain what changes were made and why
- **Testing**: Describe how changes were tested
- **Documentation**: Update relevant documentation
- **Breaking Changes**: Clearly mark any breaking changes

**PR Template:**

```markdown
## Description

Brief description of changes

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Code refactoring

## Testing

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Documentation

- [ ] Documentation updated
- [ ] Changelog updated (if needed)

## Breaking Changes

List any breaking changes or "None"
```

---

## 📖 Documentation

### Code Documentation

- **Inline Comments**: Explain complex logic and business rules
- **Docstrings**: Document all public functions, classes, and methods
- **Type Hints**: Provide complete type information

### User Documentation

When contributing features that affect users:

1. **Update README.md**: Add new features to feature list
2. **Update Guides**: Modify relevant documentation in `docs/`
3. **Add Examples**: Provide configuration examples
4. **Update Changelog**: Document changes for users

### Documentation Style

- **Clear Language**: Write for users, not developers
- **Examples**: Provide real-world usage examples
- **Screenshots**: Include UI screenshots when helpful
- **Cross-references**: Link related documentation sections

---

## 🏗️ Development Areas

### Current Priorities

1. **Enhanced Error Handling**: Improve recovery from network issues
2. **Performance Optimization**: Reduce resource usage and API calls
3. **Device Support**: Test with more LinkPlay device variants
4. **User Experience**: Simplify setup and configuration

### Architecture Improvements

- **WebSocket Support**: Real-time communication instead of polling
- **Device Capabilities**: Dynamic feature detection based on device model
- **Cloud Integration**: Optional cloud features for enhanced functionality
- **Audio Analysis**: Advanced audio processing features

### New Features

- **Room Correction**: EQ profiles for different listening environments
- **Scene Integration**: Audio scenes with multiple device coordination
- **Advanced Grouping**: Complex group topologies and routing
- **Analytics**: Usage patterns and optimization insights

---

## 🤝 Community

### Getting Help

- **GitHub Discussions**: Ask questions and share ideas
- **GitHub Issues**: Report bugs and request features
- **Home Assistant Community**: Get help from the broader community

### Communication Guidelines

- **Be Respectful**: Treat all community members with respect
- **Stay On Topic**: Keep discussions relevant to the integration
- **Search First**: Check existing issues before creating new ones
- **Provide Details**: Include relevant information in bug reports

### Code Review Process

1. **Automated Checks**: All PRs must pass automated tests
2. **Maintainer Review**: Code review by project maintainers
3. **Community Testing**: Encourage community testing of new features
4. **Documentation Review**: Ensure documentation is complete and accurate

---

## 🎯 Release Process

### Version Management

- **Semantic Versioning**: MAJOR.MINOR.PATCH format
- **Feature Releases**: Minor version bumps for new features
- **Bug Fixes**: Patch version bumps for fixes
- **Breaking Changes**: Major version bumps

### Release Checklist

- [ ] Update version in `manifest.json`
- [ ] Update `CHANGELOG.md`
- [ ] Test with multiple device types
- [ ] Update documentation
- [ ] Create GitHub release
- [ ] Notify HACS of new release

---

## 📚 Resources

### Home Assistant Development

- [Home Assistant Developer Documentation](https://developers.home-assistant.io/)
- [Integration Development](https://developers.home-assistant.io/docs/creating_integration_manifest)
- [Entity Development](https://developers.home-assistant.io/docs/core/entity/)

### WiiM/LinkPlay Resources

- [WiiM HTTP API Documentation](https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Products.pdf)
- [LinkPlay Protocol Information](https://github.com/home-assistant/core/tree/dev/homeassistant/components/linkplay)

### Development Tools

- [VS Code Home Assistant Extension](https://marketplace.visualstudio.com/items?itemName=keesschollaart.vscode-home-assistant)
- [HACS Development Documentation](https://hacs.xyz/docs/publish/start)

---

Thank you for contributing to the WiiM Audio integration! Your efforts help make Home Assistant better for everyone. 🎵
