# Contributing to WiiM Audio Integration

Thanks for your interest in contributing! This guide covers the essentials for getting started.

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**: Required for Home Assistant 2024.12+
- **Home Assistant Development Environment**: For testing
- **Git**: For version control

### Development Setup

1. **Fork and Clone**

   ```bash
   git clone https://github.com/YOUR_USERNAME/wiim.git
   cd wiim
   git remote add upstream https://github.com/mjcumming/wiim.git
   ```

2. **Development Environment**

   ```bash
   # Copy to HA development config
   ln -s /path/to/wiim/custom_components/wiim /config/custom_components/

   # Install development tools
   pip install black ruff pre-commit pytest
   pre-commit install
   ```

## 📝 Code Standards

### Code Style

- **Formatting**: `black` with 120 character line length
- **Linting**: `ruff` for code quality
- **Type Hints**: Required for all functions
- **Docstrings**: Google-style for public functions

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

### Architecture Principles

1. **Separation of Concerns**: API client, coordinator, and entities have distinct roles
2. **Async First**: All I/O operations must be asynchronous
3. **Error Handling**: Graceful degradation with user-friendly messages
4. **Speaker-Centric**: Business logic in Speaker class, entities are thin wrappers

## 🧪 Testing

### Run Tests

```bash
# All tests
pytest

# Specific test
pytest tests/test_api.py

# With coverage
pytest --cov=custom_components.wiim
```

### Manual Testing Checklist

- [ ] Device discovery (UPnP, manual)
- [ ] Basic playback controls
- [ ] Multiroom group management
- [ ] Error handling scenarios
- [ ] Home Assistant restart resilience

## 📤 Submitting Changes

### Workflow

1. **Create Feature Branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**

   - Follow code standards
   - Add tests for new functionality
   - Update documentation if needed

3. **Commit Changes**

   ```bash
   # Use conventional commit format
   git commit -m "feat: add multiroom volume synchronization"
   git commit -m "fix: handle session timeout during playback"
   ```

4. **Create Pull Request**
   - Clear title and description
   - Include testing details
   - Note any breaking changes

### Commit Message Format

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Adding or updating tests

## 🐛 Bug Reports

### Before Reporting

1. Check existing issues
2. Enable debug logging
3. Test with WiiM app to isolate issues
4. Gather relevant log entries

### Information to Include

- Home Assistant version
- Integration version
- Speaker model(s)
- Network setup details
- Steps to reproduce
- Relevant log entries

## 💡 Feature Requests

Use GitHub Discussions for feature requests. Include:

- Clear description of the feature
- Use case and benefits
- Any implementation ideas

## 🎯 Current Priorities

1. **Enhanced Error Handling**: Improve recovery from network issues
2. **Performance Optimization**: Reduce resource usage
3. **Device Support**: Test with more LinkPlay variants
4. **User Experience**: Simplify setup and configuration

## 📚 Resources

### Development References

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [WiiM API Documentation](https://www.wiimhome.com/pdf/HTTP%20API%20for%20WiiM%20Products.pdf)
- [LinkPlay API Reference](https://developer.arylic.com/httpapi/)

### Code Quality

```bash
# Format code
black custom_components/wiim/

# Lint code
ruff check custom_components/wiim/

# Run pre-commit checks
pre-commit run --all-files
```

## 🤝 Community

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and ideas
- **HA Community**: Integration support

---

Thank you for contributing to make WiiM integration better for everyone! 🎵
